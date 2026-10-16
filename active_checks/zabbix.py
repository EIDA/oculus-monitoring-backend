# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "zabbix-utils>=2.0.4",
# ]
# ///
import logging
import os
import socket

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
        sock.close()
    except OSError:
        logger.exception(
            "cannot connect to zabbix server %s:%s", ZABBIX_SERVER, ZABBIX_PORT
        )
        return False
    else:
        logger.info("zabbix server %s:%s is reachable", ZABBIX_SERVER, ZABBIX_PORT)
        return True


def send_to_zabbix(result) -> bool:
    """
    send a single HTTP code to zbx
    - if result["status"] present -> send this code (init)
    - if result["error"] indicates timeout -> send 408
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

        items = [ItemValue(result.get("node"), result.get("test"), value)]

        logger.info(
            "sending %s to zabbix for host: %s (value=%s)",
            result.get("test"),
            result.get("node"),
            value,
        )

        response = sender.send(items)

        logger.info(
            "%s/%s items sent successfully",
            getattr(response, "processed", "?"),
            getattr(response, "total", "?"),
        )

        if getattr(response, "failed", 0) > 0:
            logger.error("failed: %s items", response.failed)
            return False

    except Exception:
        logger.exception("error sending %s to zabbix")
        return False

    return True
