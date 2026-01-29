# /// script
# requires-python = "==3.12"
# dependencies = [
#     "eida-consistency==0.3.7",
#     "zabbix-utils==2.0.4",
#     "pyyaml",
# ]
# ///
import json
import logging
import os
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml
from eida_consistency.runner import run_consistency_check
from zabbix_utils import ItemValue, Sender

# config by env variables
DURATION = 600
EPOCHS = 100
MAX_WORKERS = 4
SKIP_NODES = ["IGN"]
ZABBIX_SERVER = "oculus-zabbix-zabbix-server"
ZABBIX_PORT = 10051

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

# TODO ajouter emplacement dans .env
def get_eida_nodes_directory():
    """get the local eida_nodes directory path"""
    nodes_dir = Path(__file__).parent / "eida_nodes"

    if not nodes_dir.exists():
        logger.error("eida_nodes directory not found at %s", nodes_dir)
        return None

    logger.info("using local eida_nodes directory: %s", nodes_dir)
    return nodes_dir

def list_nodes():
    """load all EIDA nodes .yaml"""
    nodes = []
    nodes_path = Path(get_eida_nodes_directory())

    for yaml_file in nodes_path.glob("*.yaml"):
        with yaml_file.open() as f:
            data = yaml.safe_load(f)
            nodes.append(data["node"])

    return nodes

def run_eida_consistency(node, epochs, duration):
    """run eida-consistency unsing python API"""
    try:
        logger.info("running consistency check for node: %s", node)
        logger.info("parameters: epochs=%s, duration=%s", epochs, duration)

        # runcheck for a specific node and get the report path
        report_path = run_consistency_check(node=node, epochs=epochs, duration=duration)

        logger.info("consitency check completed successfully")
        logger.info("report generated at: %s", report_path)

    except RuntimeError:
        logger.exception("error running eida-consistency")
        return None
    else:
        return report_path

def send_to_zabbix(hostname, json_file_path):
    """send results to zbx"""
    if not ZABBIX_SERVER:
        logger.error("ZABBIX_SERVER environment variable not set")
        return False
    try:
        # read JSON file
        with Path(json_file_path).open() as f:
            json_content = json.load(f)

        # convert JSON to string for sending
        json_string = json.dumps(json_content)

        # extract score for summùary
        score = json_content.get("summary", {}).get("score")

        if score is None:
            logger.warning("score not found i, JSOn summary")

        # connecy too zabx server
        sender = Sender(server=ZABBIX_SERVER, port=ZABBIX_PORT)

        logger.info("sending data ton zabbix for host: %s", hostname)

        # create items
        items = [
            ItemValue(hostname, "report.json", json_string),
            ItemValue(hostname, "score.eida_consistency", score),
        ]

        # se,nd via zabbix server
        response = sender.send(items)

        logger.info(
            "%s: %s/%s items sent succesfully",
            hostname,
            response.processed,
            response.total,
        )

        if response.failed > 0:
            logger.error("failed: %s items", response.failed)
            return False
    except (FileNotFoundError, json.JSONDecodeError, ConnectionError, OSError):
        logger.exception("error sending to zabbix")
        return False
    else:
        logger.info("all items sent succesfully")
        return True

def process_node(node_name, epochs, duration):
    """process one node concistency check"""
    try:
        epochs_value = epochs
        # TODO: remove when obspy 1.5 is released
        # transform EPOSFR to RESIF for eida-consistency check
        consistency_node_name = "RESIF" if node_name == "EPOSFR" else node_name

        report_path = run_eida_consistency(
            consistency_node_name,
            epochs_value,
            duration
        )

        if not report_path:
            logger.error("eida-consistency check failed for %s", consistency_node_name)
            return False

        json_file = Path(report_path)

        if not json_file.exists():
            logger.error("Report file not found: %s", json_file)
            return False

        # send to zabbix with original node name (EPOSFR)
        hostname = node_name
        logger.info("sending report to zabbix for %s", hostname)
        result = send_to_zabbix(hostname, json_file)
        if not result:
            logger.error("failed to send to zabbix for %s", hostname)

    except (FileNotFoundError, RuntimeError):
        logger.exception("error processing node %s", node_name)
        return False
    else:
        return result

def main():

    # configuration
    nodes_dir = get_eida_nodes_directory()

    if not nodes_dir:
        logger.error("eida_nodes directory not found")
        return

    logger.info("=" * 50)
    logger.info(
        "configuration: epochs=%s duration=%s, max_workers=%s",
        EPOCHS,
        DURATION,
        MAX_WORKERS,
    )
    logger.info("starting EIDA consitency checks for all nodes (parallel mode)")
    logger.info("=" * 50)

    # checl is zabbix connection first
    if not check_zabbix_connection():
        logger.error("aborting: zabbix server if not reachable")
        return

    nodes = list_nodes()

    if SKIP_NODES:
        logger.info("skipping nodes: %s", ",".join(SKIP_NODES))

    nodes = list(set(nodes) - set(SKIP_NODES))
    logger.debug("new list of nodes %s", nodes)

    # process nodes in parallel
    # TODO: remplacer par process based
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_node, n, EPOCHS, DURATION): n for n in nodes
        }

        completed = 0
        for future in as_completed(futures):
            node_name = futures[future]
            try:
                success = future.result()
                if success:
                    logger.info(
                        "%s: consistency check and zabbix sending completed",
                        node_name,
                    )
                else:
                    logger.error(
                        "%s: consistency check or zabbix sending failed", node_name
                    )
                completed += 1
            except RuntimeError:
                logger.exception("%s: unexpected error", node_name)
                completed += 1

    logger.info("=" * 50)
    logger.info("all nodes processing completed (%s/%s)", completed, len(nodes))
    logger.info("=" * 50)

if __name__ == "__main__":
    main()
