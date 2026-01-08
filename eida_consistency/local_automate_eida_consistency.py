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
# TODO remplacer par logger.ingo logger.level
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def log_and_print(message, level=logging.INFO):
    """utilities for log and print"""
    print(message)
    logger.log(level, message)


def get_eida_nodes_directory():
    """get the local eida_nodes directory path"""
    nodes_dir = Path(__file__).parent.parent / "eida_nodes"

    if not nodes_dir.exists():
        log_and_print(f"eida_nodes directory not found at {nodes_dir}", logging.ERROR)
        return None

    log_and_print(f"using local eida_nodes directory: {nodes_dir}")
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
        log_and_print(f"running consistency check for node: {node.upper()}")
        log_and_print(f"parameters: epochs={epochs}, duration={duration}")

        # runcheck for a specific node and get the report path
        report_path = run_consistency_check(node=node, epochs=epochs, duration=duration)

        log_and_print("consitency check completed successfully")
        log_and_print(f"report generated at: {report_path}")

    except RuntimeError as e:
        log_and_print(f"error running eida-consistency: {e}", logging.ERROR)
        return None
    else:
        return report_path


# TODO check env before launch of the check
def send_to_zabbix(hostname, json_file_path):
    """send results to zbx"""
    try:
        # zbx srv config
        zabbix_server = "localhost"
        zabbix_port = 10051

        if not zabbix_server:
            log_and_print("ZABBIX_SERVER environment variable not set", logging.ERROR)
            return False

        # read JSON file
        with open(json_file_path) as f:
            json_content = json.load(f)

        # convert JSON to string for sending
        json_string = json.dumps(json_content)

        # extract score for summary
        score = json_content.get("summary", {}).get("score")

        if score is None:
            log_and_print("score not found in JSON summary", logging.WARNING)

        # connect to zbx srver
        sender = Sender(server=zabbix_server, port=zabbix_port)

        log_and_print(f"sending data to zabbix for host: {hostname}")

        # create items
        items = [
            ItemValue(hostname, "report.json", json_string),
            ItemValue(hostname, "score.eida_consistency", score),
        ]

        # send via zbx server
        response = sender.send(items)

        log_and_print(
            f"{hostname}: {response.processed}/{response.total} items sent successfully"
        )

        if response.failed > 0:
            log_and_print(f"failed: {response.failed} items", logging.ERROR)
            return False
    except (FileNotFoundError, json.JSONDecodeError, ConnectionError, OSError) as e:
        log_and_print(f"error sending to zabbix:{e}", logging.ERROR)
        return False
    else:
        log_and_print("all items sent successfully")
        return True


def process_node(node_name, epochs, duration):
    """process one node cistency check"""
    try:
        # transform EPOSFR to RESIF for eida-consistency check
        # TODO: remove when obspy 1.5 is released
        consistency_node_name = "RESIF" if node_name.upper() == "EPOSFR" else node_name

        report_path = run_eida_consistency(consistency_node_name, epochs, duration)

        if not report_path:
            log_and_print(
                f"eida-consistency check failed for {consistency_node_name}",
                logging.ERROR,
            )
            return False

        json_file = Path(report_path)

        if not json_file.exists():
            log_and_print(f"Report file not found: {json_file}", logging.ERROR)
            return False

        # send to zabbix with original node name (EPOSFR)
        hostname = node_name.upper()
        return send_to_zabbix(hostname, json_file)

    except (FileNotFoundError, RuntimeError) as e:
        log_and_print(f"error processing node {node_name}: {e}", logging.ERROR)
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

    log_and_print(f"{'=' * 50}")
    log_and_print("starting EIDA consistency checks for all nodes (parallel mode)")
    log_and_print(f"{'=' * 50}")

    # get local eida_nodes directory
    nodes_dir = get_eida_nodes_directory()

    if not nodes_dir:
        log_and_print("eida_nodes directory not found", logging.ERROR)
        return

    yaml_data = load_yaml_files(nodes_dir)

    if not yaml_data:
        log_and_print(f"no yaml files found in {nodes_dir}", logging.ERROR)
        return

    log_and_print(f"found {len(yaml_data)} nodes to process")

    if skip_nodes:
        log_and_print(f"skipping nodes: {','.join([n.upper() for n in skip_nodes])}")

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
                    log_and_print(
                        f"{node_name}: consistency check and zabbix "
                        "sending completed successfully"
                    )
                else:
                    log_and_print(
                        f"{node_name}: consistency check or zabbix sending failed",
                        logging.ERROR,
                    )
                completed += 1
            except RuntimeError as e:
                log_and_print(f"{node_name}: unexpected error: {e}", logging.ERROR)
                completed += 1
    log_and_print(f"\n{'=' * 50}")
    log_and_print(f"all nodes processing completed ({completed}/{len(yaml_data)})")
    log_and_print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
