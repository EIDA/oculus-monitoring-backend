# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "pyyaml",
#     "requests",
#     "zabbix-utils",
# ]
# ///
import os
import yaml
import time
import requests
import subprocess
import shutil
import logging
from pathlib import Path
from urllib.parse import urlencode
from zabbix_utils import Sender, ItemValue

# config logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('webscenarios_perfcheck.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def log_and_print(message, level=logging.INFO):
    """utilities fot log and print"""
    print(message)
    logger.log(level, message)

def clone_repository():
    """clone the oculus-monitoring-backend repo """
    repo_url = "https://github.com/EIDA/oculus-monitoring-backend"
    clone_dir = "oculus-monitoring-backend"

    try:
        # remove existing repo if exists
        if os.path.exists(clone_dir):
            shutil.rmtree(clone_dir)

        log_and_print(f"cloning repository from {repo_url}")
        subprocess.run(['git', 'clone', repo_url, clone_dir], check=True, capture_output=True)

        nodes_dir = os.path.join(clone_dir, "eida_nodes")

        if not os.path.exists(nodes_dir):
            log_and_print(f"eida_nodes directory not found, in cloned repository")
            return None
        
        log_and_print(f"repository cloned successfully to {clone_dir}")
        return nodes_dir
    
    except subprocess.CalledProcessError as e:
        log_and_print(f"error cloning repository: {e}")
        return None
    except Exception as e:
        log_and_print(f"unexpected error during git clone: {e}")
        return None


def load_yaml_files(nodes_dir):
    """load all EIDA nodes .yaml"""
    yaml_files = {}
    nodes_path = Path(nodes_dir)

    for yaml_file in nodes_path.glob("*.yaml"):
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f)
            yaml_files[yaml_file.stem] = data

    return yaml_files

def build_url(endpoint, webservice, params):
    """build the URL for the requests"""

    # for ws wfcatalog is /eidaws/, for other is /fdsnws/
    if webservice == 'wfcatalog':
        service_path = 'eidaws'
    else:
        service_path = 'fdsnws'


    base_url = f"https://{endpoint}/{service_path}/{webservice}/1/query"

    # query parameters
    query_params = {}
    if 'net' in params and params['net']:
        query_params['net'] = params['net']
    if 'sta' in params and params['sta']:
        query_params['sta'] = params['sta']
    if 'loc' in params and params['loc']:
        query_params['loc'] = params['loc']
    if 'cha' in params and params['cha']:
        query_params['cha'] = params['cha']
    if 'start' in params and params['start']:
        query_params['start'] = params['start']
    if 'end' in params and params['end']:
        query_params['end'] = params['end']
    
    return f"{base_url}?{urlencode(query_params)}"

def make_request(url):
    """make http request"""
    temp_file_path = None
    try:
        start_time = time.time()

        headers = {
            'User-Agent': 'oculus-monitor'
        }

        # download full content with get
        response = requests.get(url, headers=headers, timeout=60, allow_redirects=True)

        end_time = time.time()
        response_time = round((end_time - start_time) * 1000, 2)

        # get size file
        content_size = len(response.content)

        return {
            'status_code': response.status_code,
            'response_time_ms': response_time,
            'content_size_bytes': content_size,
            'url': url
        }
    
    # exceltions timeout 
    except requests.exceptions.Timeout:
        return {
            'status_code': 'TIMEOUT',
            'response_time_ms': 60000,
            'content_size_bytes': 0,
            'url': url
        }
    # exception connection error
    except requests.exceptions.ConnectionError:
        return {
            'status_code': 'CONNECTION_ERROR',
            'response_time_ms': 0,
            'content_size_bytes': 0,
            'url': url
        }
    # eception request exception
    except requests.exceptions.RequestException as e:
        return {
            'status_code': 'REQUEST_ERROR',
            'response_time_ms': 0,
            'content_size_bytes': 0,
            'error': str(e),
            'url': url
        }
    except Exception as e:
        return {
            'status_code': 'ERROR',
            'response_time_ms': 0,
            'content_size_bytes': 0,
            'error': str(e),
            'url': url
        }

def send_to_zabbix(hostname, results):
    """send results to zbx srv"""
    try:
        # zbx srv config
        ZABBIX_SERVER = os.getenv('ZABBIX_SERVER')
        ZABBIX_PORT = 10051

        # connecy to zbx srv
        sender = Sender(server=ZABBIX_SERVER, port=ZABBIX_PORT)

        log_and_print(f"\nsending data to zabbix for host: {hostname}")

        items = []

        for key, metrics in results.items():
            # calculate transfer rate (bytes/s)
            transfer_rate = 0
            if metrics['response_time_ms'] > 0 and metrics['content_size_bytes'] > 0:
                # convert to seconds and calc bytes/s
                transfer_rate = round(metrics['content_size_bytes'] / (metrics['response_time_ms'] / 1000), 2)

            # key format: dataselect.9streams
            items.extend([
                ItemValue(hostname, f"{key}.status_code", str(metrics['status_code'])),
                ItemValue(hostname, f"{key}.response_time_ms", metrics['response_time_ms']),
                ItemValue(hostname, f"{key}.content_size_bytes", metrics['content_size_bytes']),
                ItemValue(hostname, f"{key}.transfer_rate", transfer_rate)
            ])

            log_and_print(f"    {key}.status_code = {metrics['status_code']}")
            log_and_print(f"    {key}.response_time_ms = {metrics['response_time_ms']}")
            log_and_print(f"    {key}.content_size_bytes = {metrics['content_size_bytes']}")
            log_and_print(f"    {key}.transfer_rate = {transfer_rate} bytes/sec")

        # send via zbx srv
        log_and_print(f"\nsending {len(items)} items to zabbix")
        response = sender.send(items)
        log_and_print(f"{hostname}: {response.processed}/{response.total} items send successfully")

        if response.failed > 0:
            log_and_print(f"    failed: {response.failed} items")
            return False
        else:
            log_and_print(f"    all items sent successfully")
            return True
    except Exception as e:
        log_and_print(f"    error sending to zabbix: {e}")
        return False


def process_node(node_name, node_data):
    """process one node and return results"""
    results = {}
    endpoint = node_data.get('endpoint')

    if not endpoint:
        log_and_print(f"no endpoint found for node {node_name}")
        return results
    
    perf_checks = node_data.get('perfCheck', [])

    for check in perf_checks:
        webservice = check.get('webservice')
        scenario = check.get('scenario')

        if not webservice or not scenario:
            continue

        url = build_url(endpoint, webservice, check)

        log_and_print(f"testing {node_name}: {webservice}.{scenario}")
        result = make_request(url)

        # store result
        key = f"{webservice}.{scenario}"
        results[key] = {
            'status_code': result['status_code'],
            'response_time_ms': result['response_time_ms'],
            'content_size_bytes': result['content_size_bytes']
        }

        log_and_print(f" -> status: {result['status_code']}, time: {result['response_time_ms']}ms, size: {result['content_size_bytes']} bytes")
    
    return results

def main():
    # load all .yaml files
    nodes_dir = clone_repository()

    if not nodes_dir:
        log_and_print("failed to clone repository or find eida_nodes directory")
        return

    yaml_data = load_yaml_files(nodes_dir)
    
    if not yaml_data:
        log_and_print(f"no yaml files found in {nodes_dir}")
        return

    for node_name, node_data in yaml_data.items():
        log_and_print(f"\n{'='*50}")
        log_and_print(f"processing node: {node_name}")
        log_and_print(f"{'='*50}")

        results = process_node(node_name, node_data)

        if results:
            # send to zbx
            hostname = node_name.upper()
            if send_to_zabbix(hostname, results):
                log_and_print(f"{node_name}: perfCheck and zabbix sending completed")
            else:
                log_and_print(f"{node_name}: perfCheck completed but zabbix sending failed")
        else:
            log_and_print(f"no results for node {node_name}")

    log_and_print(f"\nall nodes processing completed")

if __name__ == "__main__":
    main()
