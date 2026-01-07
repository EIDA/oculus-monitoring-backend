# /// script
# requires-python = "==3.14"
# dependencies = [
#     "eida-consistency==0.3.5",
#     "zabbix-utils==2.0.4",
#     "pyyaml",
# ]
# ///
import os
import logging
import json
import yaml
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from zabbix_utils import Sender, ItemValue
from eida_consistency.runner import run_consistency_check

# config logging
logging.basicConfig(
    level= logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('automate_eida_consistency.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def log_and_print(message, level=logging.INFO):
    """utilities for log and print"""
    print(message)
    logger.log(level, message)

def get_eida_nodes_directory():
    """get the local eida_nodes directory path"""
    nodes_dir = os.path.join(os.path.dirname(__file__), 'eida_nodes')

    if not os.path.exists(nodes_dir):
        log_and_print(f"eida_nodes directory not found at {nodes_dir}", logging.ERROR)
        return None
    
    log_and_print(f"using local eida_nodes directory: {nodes_dir}")
    return nodes_dir

def load_yaml_files(nodes_dir):
    """load all EIDA nodes .yaml"""
    yaml_files = {}
    nodes_path = Path(nodes_dir)

    for yaml_file in nodes_path.glob('*.yaml'):
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f)
            yaml_files[yaml_file.stem] = data
    
    return yaml_files

def run_eida_consistency(node, epochs, duration):
    """run eida-consistency unsing python API"""
    try:
        log_and_print(f"running consistency check for node: {node.upper()}")
        log_and_print(f"parameters: epochs={epochs}, duration={duration}")

        # runcheck for a specific node and get the report path
        report_path = run_consistency_check(
            node=node,
            epochs=epochs,
            duration=duration
        )

        log_and_print(f"consitency check completed successfully")
        log_and_print(f"report generated at: {report_path}")

        return report_path
    
    except Exception as e:
        log_and_print(f"error running eida-consistency: {e}", logging.ERROR)
        return None

def send_to_zabbix(hostname, json_file_path):
    """send results to zbx"""
    try:
        # zbx srv config
        ZABBIX_SERVER = os.getenv('ZABBIX_SERVER')
        ZABBIX_PORT = 10051

        if not ZABBIX_SERVER:
            log_and_print("ZABBIX_SERVER environment variable not set", logging.ERROR)
            return False
        
        # read JSON file
        with open(json_file_path, 'r') as f:
            json_content = json.load(f)

        # convert JSON to string for sending
        json_string = json.dumps(json_content)

        # extract score for summary
        score = json_content.get('summary', {}).get('score')

        if score is None:
            log_and_print("score not found in JSON summary", logging.WARNING)
        
        # connect to zbx srver
        sender = Sender(server=ZABBIX_SERVER, port=ZABBIX_PORT)

        log_and_print(f"sending data to zabbix for host: {hostname}")

        # create items
        items = [
            ItemValue(hostname, 'report.json', json_string),
            ItemValue(hostname, 'score.eida_consistency', score)
        ]

        # send via zbx server
        response = sender.send(items)

        log_and_print(f"{hostname}: {response.processed}/{response.total} items sent successfully")

        if response.failed > 0:
            log_and_print(f"failed: {response.failed} items", logging.ERROR)
            return False
        else:
            log_and_print("all items sent successfully")
            return True
    except Exception as e:
        log_and_print(f"error sending to zabbix:{e}", logging.ERROR)
        return False

def process_node(node_name, node_data, epochs, duration):
    """process one node cistency check"""
    try:
        # transform EPOSFR to RESIF for eida-consistency check
        consistency_node_name = "RESIF" if node_name.upper() == "EPOSFR" else node_name

        report_path = run_eida_consistency(consistency_node_name, epochs, duration)

        if not report_path:
            log_and_print(f"eida-consistency check failed for {consistency_node_name}", logging.ERROR)
            return False
        
        json_file = Path(report_path)

        if not json_file.exists():
            log_and_print(f"Report file not found: {json_file}", logging.ERROR)
            return False
        
        # send to zabbix with original node name (EPOSFR)
        hostname = node_name.upper()
        return send_to_zabbix(hostname, json_file)
    
    except Exception as e:
        log_and_print(f"error processing node {node_name}: {e}", logging.ERROR)
        return False

def main():
    # configuration
    epochs = 10
    duration = 600
    max_workers = 4 # number of nodes prallele
    skip_nodes = ["icgc","odc"] # exclude nodes for tests

    log_and_print(f"{'='*50}")
    log_and_print(f"starting EIDA consistency checks for all nodes (parallel mode)")
    log_and_print(f"{'='*50}")

    # get local eida_nodes directoru
    nodes_dir = get_eida_nodes_directory()

    if not nodes_dir:
        log_and_print("eida_nodes directoru not found", logging.ERROR)
        return
    
    yaml_data = load_yaml_files(nodes_dir)

    if not yaml_data:
        log_and_print(f"no yaml files found in {nodes_dir}", logging.ERROR)
        return
    
    log_and_print(f"found {len(yaml_data)} nodes to process")

    if skip_nodes:
        log_and_print(f"skipping nodes: {','.join([n.upper() for n in skip_nodes ])}")
    
    # process nodes in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_node, node_name, node_data, epochs, duration): node_name
            for node_name, node_data in yaml_data.items()
            if node_name.lower() not in  [n.lower() for n in skip_nodes]
        }

        completed = 0
        for future in as_completed(futures):
            node_name = future.result()
            try:
                sucess = future.result()
                if sucess:
                    log_and_print(f"{node_name}: consistency check and zabbix sending completed successfullyu")
                else:
                    log_and_print(f"{node_name}: consitency check or zabbix sending failed", logging.ERROR)
                completed += 1
            except Exception as e:
                log_and_print(f"{node_name}: unexpected error: {e}", logging.ERROR)
                completed += 1
    log_and_print(f"\n{'='*50}")
    log_and_print(f"all nodes processing completed ({completed}/{len(yaml_data)})")
    log_and_print(f"{'='*50}")

if __name__ == "__main__":
    main()
