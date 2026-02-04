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

# config logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)

def check_zabbix_connection():
    """check if zabbix server is reachable"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((ZABBIX_SERVER, ZABBIX_PORT))
    except OSError:
        logger.exception(
            "cannot connect to zabbix server %s:%s", ZABBIX_SERVER, ZABBIX_PORT
        )
        return False
    else:
        logger.info("zabbix server %s:%s is reachable", ZABBIX_SERVER, ZABBIX_PORT)
        return True

def get_eida_nodes_directory():
    """get the local eida_nodes directory path"""
    nodes_dir = Path(__file__).parent / "eida_nodes"

    if not nodes_dir.exists():
        logger.error("eida_nodes directory not found at %s", nodes_dir)
        return None

    logger.info("using local eida_nodes directory: %s", nodes_dir)
    return nodes_dir

def load_yaml_files(nodes_dir):
    """load all EIDA nodes .yaml"""
    yaml_files = {}
    nodes_path = Path(nodes_dir)

    for yaml_file in nodes_path.glob("*.yaml"):
        with yaml_file.open() as f:
            data = yaml.safe_load(f)
            yaml_files[yaml_file.stem] = data

    return yaml_files

def build_url(endpoint, service_name, params):
    """build the URL for requests"""

    base_url = f"https://{endpoint}/{service_name}/1/query"

    # build query parameters
    query_params = {}
    for key in ["net", "sta", "loc", "cha", "start", "end"]:
        if params.get(key):
            query_params[key] = params[key]

    # use safe parameter to rpeserve wildcards
    query_string = urlencode(query_params, safe="*:-T")

    return f"{base_url}?{query_string}"

def process_node(node_name, node_data):
    """process one node and resturn results"""
    results = {}
    endpoint = node_data.get("endpoint")

    if not endpoint:
        logger.warning("no endpoint found for node %s", node_name)
        return results

    services = node_data.get("services", [])

    for service in services:
        service_name = service.get("name")
        scenario = service.get("scenario")
        parameters = service.get("parameters", {})

        if not service_name or not scenario:
            continue

        # extract webservice from service_name (ex "fdsnws/datasemect" -> "dataselect")
        webservice = (
            service_name.split("/")[-1]
            if "/" in service_name
            else service_name
        )

        url = build_url(endpoint, service_name, parameters)

        logger.info("testing %s: %s.%s", node_name, webservice, scenario)
        logger.info("request URL: %s", url)
        result = make_request(url)

        # store result
        key = f"{webservice}.{scenario}"
        results[key] = {
            "status_code": result["status_code"],
            "response_time_ms": result["response_time_ms"],
            "content_size_bytes": result["content_size_bytes"],
        }

        logger.info(
            "-> status: %s, time: %sms, size %s bytes",
            result["status_code"],
            result["response_time_ms"],
            result["content_size_bytes"],
        )

    return results

def make_request(url):
    """make http request"""
    try:
        start_time = time.time()

        headers = {"User-Agent": "oculus-monitor"}

        # download full content with get
        response = requests.get(url, headers=headers, timeout=180, allow_redirects=True)

        end_time = time.time()
        response_time = round((end_time - start_time) * 1000, 2)

        #get size file
        content_size = len(response.content)

    # exceltions timeout
    except requests.exceptions.Timeout:
        return {
            "status_code": "TIMEOUT",
            "response_time_ms": 180000,
            "content_size_bytes": 0,
            "url": url,
        }
    # exception connection error
    except requests.exceptions.ConnectionError:
        return {
            "status_code": "CONNECTION_ERROR",
            "response_time_ms": 0,
            "content_size_bytes": 0,
            "url": url,
        }
    # exception request exception
    except requests.exceptions.RequestException as e:
        return {
            "status_code": "REQUEST_ERROR",
            "response_time_ms": 0,
            "content_size_bytes": 0,
            "error": str(e),
            "url": url,
        }
    except (OSError, ValueError) as e:
        return {
            "status_code": "ERROR",
            "response_time_ms": 0,
            "content_size_bytes": 0,
            "error": str(e),
            "url": url,
        }
    else:
        return {
            "status_code": response.status_code,
            "response_time_ms": response_time,
            "content_size_bytes": content_size,
            "url": url,
        }

def send_to_zabbix(hostname, results):
    """send results to zbx server"""
    try:
        # connect to zbx srv
        sender = Sender(server=ZABBIX_SERVER, port=ZABBIX_PORT)

        logger.info("sending data to zabbix for host: %s", hostname)

        items = []

        for key, metrics in results.items():
            # calculate transfer rate (bytes/s)
            transfer_rate = 0
            if metrics["response_time_ms"] > 0 and metrics["content_size_bytes"] > 0:
                # convert to seconds and calc bytes/s
                transfer_rate = round(
                    metrics["content_size_bytes"]
                    / (metrics["response_time_ms"] / 1000),
                    2,
                )

            # key format: dataselect.9streams
            items.extend(
                [
                    ItemValue(
                        hostname,
                        f"{key}.status_code",
                        str(metrics["status_code"])
                    ),
                    ItemValue(
                        hostname,
                        f"{key}.response_time_ms",
                        metrics["response_time_ms"]
                    ),
                    ItemValue(
                        hostname,
                        f"{key}.content_size_bytes",
                        metrics["content_size_bytes"],
                    ),
                    ItemValue(
                        hostname,
                        f"{key}.transfer_rate",
                        transfer_rate
                    ),
                ]
            )

            logger.info("   %s.status_code = %s",
                        key,
                        metrics["status_code"])
            logger.info("   %s.response_time_ms = %s",
                        key,
                        metrics["response_time_ms"])
            logger.info("   %s.content_size_bytes = %s",
                        key,
                        metrics["content_size_bytes"])
            logger.info("   %s.transfer_rate = %s bytes/sec",
                        key,
                        transfer_rate)

        # send via zbx srv
        logger.info("sending %s items to zabbix", len(items))
        response = sender.send(items)
        logger.info(
            "%s: %s/%s items send successfully",
            hostname,
            response.processed,
            response.total
        )

        if response.failed > 0:
            logger.error("failed: %s items", response.failed)
            # show failed items
            if hasattr(response, "failed_items"):
                for failed_item in response.failed_items:
                    logger.error(" - failed item: %s", failed_item)
            return False
    except Exception:
        logger.exception("error sending to zabbix")
        return False
    else:
        logger.info("all items sent successfully")
        return True

def main():
    logger.info("=" * 50)
    logger.info("starting EIDA webscenarios performance checks")
    logger.info("=" * 50)

    # check if zabbix connections first
    if not check_zabbix_connection():
        logger.error("aborting: zabbix server is not reachable")
        return

    # load all .yaml files
    nodes_dir = get_eida_nodes_directory()

    if not nodes_dir:
        logger.error("failed to find eida_nodes directory")
        return

    yaml_data = load_yaml_files(nodes_dir)

    if not yaml_data:
        logger.error("no yaml files found in %s", nodes_dir)
        return

    for node_name, node_data in yaml_data.items():
        logger.info("=" * 50)
        logger.info("processing node: %s", node_name)
        logger.info("=" * 50)

        results = process_node(node_name, node_data)

        if results:
            # send to zbx
            hostname = node_name.upper()
            if send_to_zabbix(hostname, results):
                logger.info(
                    "%s: perfCheck and zabbix sending completed",
                    node_name
                )
            else:
                logger.error(
                    "%s: perfCheck complated but zabbix sending failed",
                    node_name
                )
        else:
            logger.warning("no results for node %s", node_name)

    logger.info("=" * 50)
    logger.info("all nodes processing completed")
    logger.info("=" * 50)

if __name__ == "__main__":
    main()
