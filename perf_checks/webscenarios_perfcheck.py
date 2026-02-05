# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pathlib>=1.0.1",
#     "pyyaml>=6.0.3",
#     "requests>=2.32.5",
#     "zabbix-utils>=2.0.4",
# ]
# ///
import logging
import os
import socket
import time
from pathlib import Path
from urllib.parse import urlencode

import requests
import yaml
from zabbix_utils import ItemValue, Sender

# config env variables
ZABBIX_SERVER = os.getenv("ZABBIX_SERVER", "localhost")
ZABBIX_PORT = int(os.getenv("ZABBIX_PORT", "10051"))
HTTP_OK = 200
SEPARATOR = "=" * 50

# config logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)

def check_zabbix_connection():
    """check fi zabbix server is reachable"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((ZABBIX_SERVER, ZABBIX_PORT))
        sock.close()
    except OSError:
        logger.exception("cannot connect to zabbix server %s:%s",
                        ZABBIX_SERVER,
                        ZABBIX_PORT)
        return False
    else:
        logger.info("zabbix server %s:%s is reachable",
                    ZABBIX_SERVER,
                    ZABBIX_PORT)
        return True

def load_yaml_files(nodes_dir):
    """load all  EIDA nodes .yaml from directory"""
    yaml_files = {}
    for yaml_file in Path(nodes_dir).glob("*.yaml"):
        with yaml_file.open() as f:
            yaml_files[yaml_file.stem] = yaml.safe_load(f)
    return yaml_files

def build_url(endpoint, service_name, params):
    """build the URL for requests with query parameters"""
    base_url = f"https://{endpoint}/{service_name}/1/query"
    # exctratr only relevant parameters
    query_params = {
        key: params[key]
        for key in ["net", "sta", "loc", "cha", "start", "end"]
        if params.get(key)
    }
    # perserve wildcards and ISO 8601 datetime format
    query_string = urlencode(query_params, safe="*:-T")
    return f"{base_url}?{query_string}"

def make_request(url):
    """make HTTP request and return metrics"""
    try:
        start_time = time.time()
        response = requests.get(
            url,
            headers={"User-Agent": "oculus-monitor"},
            timeout=180,
            allow_redirects=True
        )
        reponse_time = round((time.time() - start_time) * 1000, 2)
        return {
            "status_code": response.status_code,
            "response_time_ms": reponse_time,
            "content_size_bytes": len(response.content),
        }
    except requests.exceptions.Timeout:
        logger.exception("request timeout for %s", url)
        return {"status_code": "TIMEOUT",
                "response_time_ms": 180000,
                "content_size_bytes": 0}
    except requests.exceptions.ConnectionError:
        logger.exception("connection error for %s", url)
        return {"status_code": "CONNECTION_ERROR",
                "response_time_ms": 0,
                "content_size_bytes": 0}
    except requests.exceptions.RequestException:
        logger.exception("request error for %s", url)
        return {"status_code": "REQUEST_ERROR",
                "response_time_ms": 0,
                "content_size_bytes": 0}
    except(OSError, ValueError):
        logger.exception("error for %s", url)
        return {"status_code": "ERROR",
                "response_time_ms": 0,
                "content_size_bytes": 0}

def process_node(node_name, node_data):
    """process one node and return results"""
    results = {}
    endpoint = node_data.get("endpoint")

    if not endpoint:
        logger.warning("no endpoint found for node %s", node_name)
        return results

    #iterate through all services defined for this node
    for service in node_data.get("services", []):
        service_name = service.get("name")
        scenario = service.get("scenario")
        parameters = service.get("parameters", {})

        if not service_name or not scenario:
            continue

        # extract webservice from service_name(e.g. "fdsnws/dataselect" -> "dataselect")
        webservice = service_name.split("/")[-1]
        url = build_url(endpoint, service_name, parameters)
        key = f"{webservice}.{scenario}"

        logger.info("testing %s: %s", node_name, key)
        logger.info("request URL: %s", url)
        result = make_request(url)

        # store only status code if not 200, otherwise store all metrics
        if result["status_code"] == HTTP_OK:
            results[key] = result
        else:
            results[key] = {"status_code": result["status_code"]}

        logger.info(
            "-> status: %s, time: %sms, size: %s bytes",
            result["status_code"],
            result.get("response_time_ms", "N/A"),
            result.get("content_size_bytes", "N/A")
        )

    return results

def send_to_zabbix(hostname, results):
    """send results to zabbix server"""
    try:
        sender = Sender(server=ZABBIX_SERVER, port=ZABBIX_PORT)
        logger.info("sending data to zabbix for host: %s", hostname)
        items = []

        for key, metrics in results.items():
            # alwways send status code
            items.append(
                ItemValue(hostname, f"{key}.status_code", str(metrics["status_code"]))
            )

            # sen,d response_time_ms and content_size_bytes only if they exist
            if "response_time_ms" in metrics and "content_size_bytes" in metrics:
                # calculate transfer rate
                transfer_rate = 0
                if (
                    metrics["response_time_ms"] > 0
                    and metrics["content_size_bytes"] > 0
                ):
                    response_time_sec = metrics["response_time_ms"] / 1000
                    transfer_rate = round(
                        metrics["content_size_bytes"] / response_time_sec,
                        2
                    )

                items.extend([
                    ItemValue(hostname, f"{key}.response_time_ms",
                            metrics["response_time_ms"]),
                    ItemValue(hostname, f"{key}.content_size_bytes",
                            metrics["content_size_bytes"]),
                    ItemValue(hostname, f"{key}.transfer_rate",
                            transfer_rate),
                ])

                logger.info("   %s.response_time_ms = %s",
                            key,
                            metrics["response_time_ms"])
                logger.info("   %s.content_size_bytes = %s",
                            key,
                            metrics["content_size_bytes"])
                logger.info("   %s.transfer_rate = %s bytes/sec",
                            key,
                            transfer_rate)

            logger.info("   %s.status_code = %s", key, metrics["status_code"])

        logger.info("sending %s items to zabbix", len(items))
        response = sender.send(items)
        logger.info(
            "%s: %s/%s items, sent successfully",
            hostname,
            response.processed,
            response.total
        )

        if response.failed > 0:
            logger.error("failed: %s items", response.failed)
            return False
    except Exception:
        logger.exception("error sendinf to zabbix")
        return False
    else:
        return True

def main():
    logger.info(SEPARATOR)
    logger.info("starting EIDA webscenarios paerfoamce checks")
    logger.info(SEPARATOR)

    # check zabbix connection
    if not check_zabbix_connection():
        logger.error("aborting: zabbix server is not reachable")
        return

    # load eida nodes directory
    nodes_dir = Path(__file__).parent / "eida_nodes"
    if not nodes_dir.exists():
        logger.error("eida_nodes directory not found at %s", nodes_dir)
        return

    logger.info("using local eida_nodes directory: %s", nodes_dir)
    yaml_data = load_yaml_files(nodes_dir)

    if not yaml_data:
        logger.error("no yaml files found in %s", nodes_dir)
        return

    # process each node
    for node_name, node_data in yaml_data.items():
        logger.info(SEPARATOR)
        logger.info("processing node: %s", node_name)
        logger.info(SEPARATOR)

        results = process_node(node_name, node_data)

        if results:
            if send_to_zabbix(node_name.upper(), results):
                logger.info("%s: perfCheck and zabbix sending completed",
                            node_name)
            else:
                logger.error("%s: perfCheck completed but zabbix sending failed",
                            node_name)
        else:
            logger.warning("no results for node %s", node_name)

    logger.info(SEPARATOR)
    logger.info("all nodes processing completed")
    logger.info(SEPARATOR)

if __name__ == "__main__":
    main()

