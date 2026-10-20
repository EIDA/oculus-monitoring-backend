# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "pathlib>=1.0.1",
#     "pyyaml>=6.0.3",
#     "requests>=2.34.2",
#     "zabbix-utils>=2.0.4",
# ]
# ///
import logging
import os
import time
from pathlib import Path
from urllib.parse import urlencode

import requests
import yaml
import zabbix

# config env variables
ZABBIX_SERVER = os.getenv("ZABBIX_SERVER", "localhost")
ZABBIX_PORT = int(os.getenv("ZABBIX_PORT", "10051"))
SKIP_NODES = os.getenv("SKIP_NODES", "").split(",")
TIMEOUT = float(os.getenv("TIMEOUT", "30.0"))
SEPARATOR = "=" * 50

SERVICES = os.getenv(
    "SERVICES",
    "fdsnws/availability/1,fdsnws/dataselect/1,fdsnws/station/1,eidaws/wfcatalog/1",
).split(",")


# config logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)


def service_to_zbx(service):
    """
    from a service name, generate a zabbix key prefix
    params:
    - service: the path of one service ex: fdsnws/station/1/
    return: zabbix key prefix
    """
    parts = service.lstrip("/").split("/")
    if len(parts) >= 2:
        return parts[1]
    return ""


def load_yaml_files(nodes_dir):
    """load all EIDA nodes .yaml from directory"""
    yaml_files = {}

    for yaml_file in Path(nodes_dir).glob("*.yaml"):
        node_name = yaml_file.stem

        # skip nodes in SKIP_NODES list
        if node_name.upper() in [node.upper() for node in SKIP_NODES]:
            logger.debug("skipping yaml file for node: %s", node_name)
            continue

        with yaml_file.open() as file:
            yaml_files[node_name] = yaml.safe_load(file)

    return yaml_files


def check_webservice(
    url: str,
    online_check: dict | None = None,
    timeout: float = TIMEOUT,
) -> dict:
    """check a webservice and run its HTTP status code"""
    result = {"url": url, "test": "", "status": None, "error": None, "elapsed": 0}
    if online_check:
        url = f"{url.rstrip('/')}/query"

        params = {
            "net": online_check["net"],
            "sta": online_check["sta"],
            "loc": online_check["loc"],
            "cha": online_check["cha"],
            "start": online_check["start"],
            "end": online_check["end"],
        }

        url = f"{url}?{urlencode(params, safe=':')}"

    start = time.monotonic()

    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "oculus-monitor/4.0"},
        )
        result["status"] = response.status_code
        result["ok"] = response.ok

    except requests.RequestException as exc:
        result["error"] = str(exc)

    finally:
        result["elapsed"] = time.monotonic() - start

    return result


def log_result(result):
    """log result of webservice check"""
    if result.get("error"):
        logger.error(
            "%s -> ERROR: %s(%.2fs)",
            result["url"],
            result["error"],
            result["elapsed"],
        )
    else:
        status_text = "OK" if result["ok"] else "FAIL"

        logger.info(
            "%s -> %s (status=%s, %.2fs)",
            result["url"],
            status_text,
            result["status"],
            result["elapsed"],
        )


def after_task(result):
    log_result(result)
    try:
        zabbix.send_to_zabbix(result)
    except Exception:
        logger.exception(
            "failed sending %s status to zabbix fos %s", result["test"], result["node"]
        )


def run_task(node, endpoint, online_check):
    """run all configured webservices check for one node"""
    results = []

    for service in SERVICES:
        url = f"https://{endpoint.rstrip('/')}/{service}/"

        result1 = check_webservice(url)
        result1["node"] = node
        result1["test"] = service_to_zbx(service) + ".healthcheck_v4"
        after_task(result1)

        result2 = check_webservice(url, online_check)
        result2["node"] = node
        result2["test"] = service_to_zbx(service) + ".short_request"
        after_task(result2)

        result3 = check_webservice(url + "application.wadl")
        result3["node"] = node
        result3["test"] = service_to_zbx(service) + ".application.wadl"
        after_task(result3)

        results += [result1, result2, result3]
    return results


def log_summary(results):
    """log aggreagate results for all checks"""
    total = len(results)
    oks = sum(1 for result in results if result.get("ok"))
    fails = sum(
        1
        for result in results
        if result.get("status") is not None and not result.get("ok")
    )
    errors = sum(1 for result in results if result.get("error"))

    logger.info(SEPARATOR)
    logger.info("summary: total=%s OK=%s FAIL=%s ERROR=%s", total, oks, fails, errors)
    logger.info(SEPARATOR)


def main():
    nodes_dir = Path(__file__).parent / "eida_nodes"

    logger.info(SEPARATOR)
    logger.info("starting checks")
    logger.info(SEPARATOR)

    if not zabbix.check_zabbix_connection():
        logger.error("aborting: zabbix server is not reachable")
        return
    results = []
    nodes = load_yaml_files(nodes_dir)
    for node in nodes.values():
        results += run_task(
            node.get("node"), node.get("endpoint"), node.get("onlineCheck")
        )

    log_summary(results)


if __name__ == "__main__":
    main()
