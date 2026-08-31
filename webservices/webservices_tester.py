# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "argparse>=1.4.0",
#     "logging>=0.4.9.6",
#     "pathlib>=1.0.1",
#     "pyyaml>=6.0.3",
#     "requests>=2.34.2",
#     "zabbix-utils>=2.0.4",
# ]
# ///
import logging
import os
import socket
import time
from pathlib import Path

import requests
import yaml
from zabbix_utils import ItemValue, Sender

# config env variables
ZABBIX_SERVER = os.getenv("ZABBIX_SERVER", "localhost")
ZABBIX_PORT = int(os.getenv("ZABBIX_PORT", "10051"))
SKIP_NODES = os.getenv("SKIP_NODES", "").split(",")
TIMEOUT = float(os.getenv("TIMEOUT", "10.0"))
SEPARATOR = "=" * 50

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
        sock.close()
    except OSError:
        logger.exception(
            "cannot connect to zabbix server %s:%s", ZABBIX_SERVER, ZABBIX_PORT
        )
        return False
    else:
        logger.info("zabbix server %s:%s is reachable", ZABBIX_SERVER, ZABBIX_PORT)
        return True


def send_to_zabbix(hostname, result) -> bool:
    """
    Send a single HTTP code to zabbix (item 'availability.healtcheck_v4')
    - if result['status'] present -> sends this code (int)
    - if result['error'] indicates timeout -> send 408
    - other -> send 500
    """
    if not ZABBIX_SERVER:
        logger.error("ZABBIX_SERVER environment variable not set")
        return False
    try:
        sender = Sender(server=ZABBIX_SERVER, port=ZABBIX_PORT)

        status = result.get("status") if isinstance(result, dict) else None
        if status is not None:
            try:
                value = int(status)
            except (TypeError, ValueError):
                value = 500
        elif isinstance(result, dict) and result.get("error"):
            err_text = str(result.get("error")).lower()
            value = 408 if "timeout" in err_text or "timed out" in err_text else 500
        else:
            value = 500

        host_up = hostname.upper()
        items = [ItemValue(host_up, "availability.healtcheck_v4", value)]

        logger.info(
            "sending availability to zabbix for host: %s (value=%s)", host_up, value
        )
        response = sender.send(items)

        logger.info(
            "%s: %s/%s items sent successfully",
            host_up,
            getattr(response, "processed", "?"),
            getattr(response, "total", "?"),
        )

        if getattr(response, "failed", 0) > 0:
            logger.error("failed: %s items", response.failed)
            return False
    except Exception:
        logger.exception("error sending availability to zabbix")
        return False

    return True


def load_yaml_files(nodes_dir):
    """load all EIDA nodes .yaml from directory"""
    yaml_files = {}
    for yaml_file in Path(nodes_dir).glob("*.yaml"):
        node_name = yaml_file.stem

        # skip nodes in SKIP_NODES list
        if node_name.upper() in [node.upper() for node in SKIP_NODES]:
            logger.debug("skipping yaml file for node: %s", node_name)
            continue

        with yaml_file.open() as f:
            yaml_files[node_name] = yaml.safe_load(f)

    return yaml_files


def check_availability(endpoint: str, timeout: float = TIMEOUT) -> dict:
    url = f"https://{endpoint.rstrip('/')}/fdsnws/availability/1/"
    start = time.monotonic()
    out = {"url": url, "status": None, "ok": False, "elapsed": None, "error": None}
    headers = {"User-Agent": "oculus-monitor/4.0"}
    try:
        resp = requests.get(url, timeout=timeout, headers=headers)
        out["status"] = resp.status_code
        out["ok"] = resp.ok
    except requests.RequestException as exc:
        out["error"] = str(exc)
    finally:
        out["elapsed"] = time.monotonic() - start
    return out


def main():
    # default values
    nodes_dir = Path(__file__).parent / "eida_nodes"

    logger.info(SEPARATOR)
    logger.info("starting checks")
    logger.info(SEPARATOR)

    # check zabbix connection
    if not check_zabbix_connection():
        logger.error("aborting: zabbix server is not reachable")
        return

    yaml_files = load_yaml_files(nodes_dir)
    tasks = []
    for node_name, node_data in yaml_files.items():
        endpoint = node_data.get("endpoint")
        if not endpoint:
            logger.warning("no 'endpoint' in %s", node_name)
            continue
        tasks.append((node_name.upper(), node_name, endpoint))

    if not tasks:
        logger.warning("no endpoint to test.")
        return

    results = []
    for fname, node, endpoint in tasks:
        try:
            res = check_availability(endpoint, TIMEOUT)
        except Exception as exc:
            logger.exception("[%s] %s -> EXCEPTION", fname, endpoint)
            results.append((fname, node, endpoint, {"error": str(exc)}))
            try:
                send_to_zabbix(node, {"error": str(exc)})
            except Exception:
                logger.exception("failed sending error status to zabbix for %s", node)
            continue

        if res.get("error"):
            logger.error(
                "[%s] %s -> ERROR: %s (%.2fs)",
                fname,
                res["url"],
                res["error"],
                res["elapsed"],
            )
        else:
            status_text = "OK" if res["ok"] else "FAIL"
            logger.info(
                "[%s] %s -> %s (status=%s, %.2fs)",
                fname,
                res["url"],
                status_text,
                res["status"],
                res["elapsed"],
            )

        try:
            send_to_zabbix(node, res)
        except Exception:
            logger.exception("failed sending availability to zabbix for %s", node)

        results.append((fname, node, endpoint, res))

    # resume
    total = len(results)
    oks = sum(1 for _f, _n, _e, r in results if r.get("ok"))
    fails = sum(1 for _f, _n, _e, r in results if r.get("status") and not r.get("ok"))
    errors = sum(1 for _f, _n, _e, r in results if r.get("error"))
    logger.info(SEPARATOR)
    logger.info("resume: total=%s OK=%s FAIL=%s ERROR=%s", total, oks, fails, errors)
    logger.info(SEPARATOR)


if __name__ == "__main__":
    main()
