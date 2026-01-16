# /// script
# requires-python = "==3.12"
# dependencies = [
#     "eida-consistency==0.3.5",
#     "zabbix-utils==2.0.4",
#     "pyyaml",
#     "dotenv>=0.9.9",
# ]
# ///
import contextlib
import json
import logging
import os
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv
from eida_consistency.runner import run_consistency_check
from zabbix_utils import ItemValue, Sender

DEFAULT_STATIONS_DIR = Path(__file__).parent / "stations"
DEFAULT_NETWORKS_DIR = Path(__file__).parent / "networks"
MIN_NETWORK_CODE_LENGTH = 2

def fetch_and_save_networks_for_node(node_name, node_data, outdir=DEFAULT_NETWORKS_DIR):
    """fetch ans save network list for a specific node"""
    out_path= Path(outdir)
    out_path.mkdir(exist_ok=True)

    base_endpoint = node_data.get("endpoint")
    if not base_endpoint:
        logger.warning("no station endpoint found for node %s", node_name)
        return None

    url = f"https://{base_endpoint}/fdsnws/station/1/query"
    out_file = out_path / f"{node_name}_network.txt"

    params = {"level": "network", "format": "text"}
    headers = {"Accept": "text/plain"}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        out_file.write_text(resp.text, encoding="utf-8")
        logger.info("network list for %s saved to %s", node_name, out_file)
        return str(out_file)
    except requests.RequestException:
        logger.exception(
            "failed to fetch network list from %s for node %s",
            url,
            node_name)
        return None

def parse_networks_from_file(networks_file):
    """parse and extract unique network codes from a network file"""
    networks = set()
    with Path(networks_file).open() as f:
        for line in f:
            stripped_line = line.strip()
            if len(stripped_line) >= MIN_NETWORK_CODE_LENGTH:
                network_code = stripped_line[:MIN_NETWORK_CODE_LENGTH]
                # filter out invalid network code (only alpganuméric)
                if network_code.isalnum() and not network_code.startswith("#"):
                    networks.add(network_code)
    return networks

def fetch_station_by_network(node_name, node_data, networks_file):
    """fetch stations list for each entwork from a network file"""
    base_endpoint = node_data.get("endpoint")
    if not base_endpoint:
        logger.warning("no station endpoint found for node %s", node_name)
        return False

    try:
        networks = parse_networks_from_file(networks_file)

        if not networks:
            logger.warning("no networks found in %s", networks_file)
            return False

        logger.info(
            "found %s unique networks for %s: %s",
            len(networks),
            node_name,
            ",".join(sorted(networks)))

        url = f"https://{base_endpoint}/fdsnws/station/1/query"
        headers = {"Accept": "text/plain"}

        # single output file for all network oh this node
        out_file = DEFAULT_STATIONS_DIR / f"{node_name}_stations.txt"
        DEFAULT_STATIONS_DIR.mkdir(exist_ok=True, parents=True)

        all_stations = []

        for network_code in sorted(networks):
            params = {"network": network_code, "level": "channel", "format": "text"}

            try:
                resp = requests.get(url, params=params, headers=headers, timeout=30)
                resp.raise_for_status()
                filtered_lines = [
                    line for line in resp.text.split("\n")
                    if line.strip() and not line.strip().startswith("#")
                ]
                all_stations.append("\n".join(filtered_lines))
                logger.info("stationlist for %s|%s saved", node_name, network_code)
            except requests.RequestException:
                logger.warning(
                    "failled to fetch stations for %s|%s from %s",
                    node_name,
                    network_code, url)
                continue
        # write all stations to fingle file
        if all_stations:
            out_file.write_text("\n".join(all_stations), encoding="utf-8")
            logger.info("marged stations list for %s savec to %s", node_name, out_file)

    except (FileNotFoundError, OSError):
        logger.exception("error reading networks file: %s", networks_file)
        return False
    else:
        return True

def fetch_all_networks_and_stations(yaml_data):
    """fetch network lists and station lists for all networks of each node"""
    logger.info("fetching network and station lists for all nodes...")

    # first, fetch all network lists
    networks_files = {}
    for node_name, node_data in yaml_data.items():
        if node_name.lower() not in [n.lower() for n in SKIP_NODES]:
            result = fetch_and_save_networks_for_node(node_name, node_data)
            networks_files[node_name] = result

    # then fetch station for each netwoek
    for node_name, network_file in networks_files.items():
        if network_file and node_name in yaml_data:
            fetch_station_by_network(node_name, yaml_data[node_name], network_file)

# load .env file
with contextlib.suppress(FileNotFoundError):
    load_dotenv()

# config logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)

# config by env variables
DURATION = int(os.getenv("EIDA_CONSISTENCY_DURATION", "600"))
EPOCHS = int(os.getenv("EIDA_CONSISTENCY_EPOCHS", "10"))
MAX_WORKERS = int(os.getenv("EIDA_CONSISTENCY_MAX_WORKERS", "4"))
SKIP_NODES = os.getenv("EIDA_CONSISTENCY_SKIP_NODES", "icgc,odc,ign").split(",")
ZABBIX_SERVER = os.getenv("ZABBIX_SERVER", "localhost")
ZABBIX_PORT = int(os.getenv("ZABBIX_PORT", "10051"))

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
    nodes_dir = Path(__file__).parent.parent / "eida_nodes"

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

def run_eida_consistency(node, epochs, duration):
    """run eida-consistency unsing python API"""
    try:
        logger.info("running consistency check for node: %s", node.upper())
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
    """process one node cistency check"""
    try:
        # TODO: remove when obspy 1.5 is released
        # transform EPOSFR to RESIF for eida-consistency check
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
        logger.info("sendinf report to zabbix for %s", hostname)
        result = send_to_zabbix(hostname, json_file)
        if not result:
            logger.error("failed to send to zabbix for %s", hostname)

    except (FileNotFoundError, RuntimeError):
        logger.exception("error processing node %s", node_name)
        return False
    else:
        return result

def main():

    nodes_dir = get_eida_nodes_directory()

    if not nodes_dir:
        logger.error("eida_nodes directory not found")
        return

    yaml_data = load_yaml_files(nodes_dir)

    if not yaml_data:
        logger.error("no yaml files found in %s", nodes_dir)
        return

    fetch_all_networks_and_stations(yaml_data)

    logger.info("=" * 50)
    # configuration
    # TODO calculer nombre d'époque en % du nombre de cha publié par le ws station du node
    # TODO faire une requete au format txt du ws station, level = channel, et prendre 2/%
    # TODO une variable d'environement pour la duration et le nombre d'epoche
    # TODO récupérer une liste des noeux par variable d'environement

    logger.info("=" * 50)
    logger.info(
        "configuration: epochs=%s, duration=%s, max_workers=%s",
        EPOCHS,
        DURATION,
        MAX_WORKERS,
    )
    logger.info("starting EIDA consistency checks for all nodes (parallel mode)")
    logger.info("=" * 50)

    # checl is zabbix connection first
    if not check_zabbix_connection():
        logger.error("aborting: zabbix server if not reachable")
        return

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

    if SKIP_NODES:
        logger.info("skipping nodes: %s", ",".join([n.upper() for n in SKIP_NODES]))

    # process nodes in parallel
    # TODO: remplacer par process based
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_node, node_name, EPOCHS, DURATION): node_name
            for node_name, node_data in yaml_data.items()
            if node_name.lower() not in [n.lower() for n in SKIP_NODES]
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
    logger.info("all nodes processing completed (%s/%s)", completed, len(yaml_data))
    logger.info("=" * 50)

if __name__ == "__main__":
    main()
