# /// script
# requires-python = "==3.12"
# dependencies = [
#     "eida-consistency==0.3.5",
#     "zabbix-utils==2.0.4",
#     "pyyaml",
# ]
# ///
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml
from eida_consistency.runner import run_consistency_check
from zabbix_utils import ItemValue, Sender

# config logging
# TODO remplacer par logger.info logger.level
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)


def get_eida_nodes_directory():
    """get the local eida_nodes directory path"""
    nodes_dir = Path(__file__).parent.parent / "eida_nodes"

    if not nodes_dir.exists():
        logger.error("eida_nodes directory not found at {nodes_dir}")
        return None

    logger.info("using local eida_nodes directory: {nodes_dir}")
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


def run_eida_consistency(node, epochs, duration):
    """run eida-consistency unsing python API"""
    try:
        logger.info("running consistency check for node: {node.upper()}")
        logger.info("parameters: epochs={epochs}, duration={duration}")

        # runcheck for a specific node and get the report path
        report_path = run_consistency_check(node=node, epochs=epochs, duration=duration)

        logger.info("consitency check completed successfully")
        logger.info("report generated at: {report_path}")

    except RuntimeError:
        logger.exception("error running eida-consistency")
        return None
    else:
        return report_path


# TODO check env before launch of the check
def send_to_zabbix(hostname, json_file_path):
    """send results to zbx"""
    try:
        # zbx srv config
        zabbix_server = os.getenv("ZABBIX_SERVER")
        zabbix_port = 10051

        if not zabbix_server:
            logger.error("ZABBIX_SERVER environment variable not set")
            return False

        # read JSON file
        with Path(json_file_path).open() as f:
            json_content = json.load(f)

        # convert JSON to string for sending
        json_string = json.dumps(json_content)

        # extract score for summary
        score = json_content.get("summary", {}).get("score")

        if score is None:
            logger.warning("score not found in JSON summary")

        # connect to zbx srver
        sender = Sender(server=zabbix_server, port=zabbix_port)

        logger.info("sending data to zabbix for host: %s", hostname)

        # create items
        items = [
            ItemValue(hostname, "report.json", json_string),
            ItemValue(hostname, "score.eida_consistency", score),
        ]

        # send via zbx server
        response = sender.send(items)

        logger.info(
            "%s: %s/%s items sent successfully",
            hostname,
            response.processed,
            response.total,
        )

        if response.failed > 0:
            logger.error("failed: {response.failed} items")
            return False
    except (FileNotFoundError, json.JSONDecodeError, ConnectionError, OSError):
        logger.exception("error sending to zabbix")
        return False
    else:
        logger.info("all items sent successfully")
        return True


def process_node(node_name, epochs, duration):
    """process one node cistency check"""
    try:
        # transform EPOSFR to RESIF for eida-consistency check
        # TODO: remove when obspy 1.5 is released
        consistency_node_name = "RESIF" if node_name.upper() == "EPOSFR" else node_name

        report_path = run_eida_consistency(consistency_node_name, epochs, duration)

        if not report_path:
            logger.error("eida-consistency check failed for %s", consistency_node_name)
            return False

        json_file = Path(report_path)

        if not json_file.exists():
            logger.error("Report file not found: %s", json_file)
            return False

        # send to zabbix with original node name (EPOSFR)
        hostname = node_name.upper()
        return send_to_zabbix(hostname, json_file)

    except (FileNotFoundError, RuntimeError):
        logger.exception("error processing node %s", node_name)
        return False


def main():
    # configuration
    epochs = 10
    # TODO calculer nombre d'époque en % du nombre de cha publié par le ws station du node
    # TODO faire une requete au format txt du ws station, level = channel, et prendre 2/%
    # TODO une variable d'environement pour le pourcentage d'époque
    duration = 600
    max_workers = 4  # number of nodes prallele
    skip_nodes = ["icgc", "odc", "ign"]  # exclude nodes for tests
    # TODO récupérer une liste des noeux par variable d'environement

    logger.info("=" * 50)
    logger.info("starting EIDA consistency checks for all nodes (parallel mode)")
    logger.info("=" * 50)

    # get local eida_nodes directory
    nodes_dir = get_eida_nodes_directory()

    if not nodes_dir:
        logger.error("eida_nodes directory not found")
        return

    yaml_data = load_yaml_files(nodes_dir)

    if not yaml_data:
        logger.error("no yaml files found in %s", nodes_dir)
        return

    logger.info("found %s nodes to process", len(yaml_data))

    if skip_nodes:
        logger.info("skipping nodes: %s", ",".join([n.upper() for n in skip_nodes]))

    # process nodes in parallel
    # TODO: remplacer par process based
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_node, node_name, epochs, duration): node_name
            for node_name, node_data in yaml_data.items()
            if node_name.lower() not in [n.lower() for n in skip_nodes]
        }

        completed = 0
        for future in as_completed(futures):
            node_name = futures[future]
            try:
                success = future.result()
                if success:
                    logger.info(
                        "%s: consistency check and zabbix sending completed successfully",
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
    logger.info("all nodes processing completed (%s/%s)", completed, len(yaml_data))
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
