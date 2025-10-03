# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "itemvalue",
#     "os",
#     "path",
#     "requests",
#     "sender",
#     "shutil",
#     "subprocess",
#     "tempfile",
#     "time",
#     "urlencode",
#     "yaml",
# ]
# ///

import os
import yaml
import time
import requests
import subprocess
import shutil
from pathlib import Path
from urllib.parse import urlencode
import tempfile
from zabbix_utils import Sender, ItemValue

def clone_repository():
    """clone the oculus-monitoring-backend repo"""
    repo_url = "https://github.com/EIDA/oculus-monitoring-backend"
    clone_dir = "oculus-monitoring-backend"

    try:
        # remove existing repo if exists
        if os.path.exists(clone_dir):
            shutil.rmtree(clone_dir)

        print(f"cloning repository from {repo_url}")
        subprocess.run(['git', 'clone', repo_url, clone_dir], check=True, capture_output=True)

        nodes_dir = os.path.join(clone_dir, "eida_nodes")

        if not os.path.exists(nodes_dir):
            print(f"eida_nodes directory not found, in cloned repository")
            return None
        
        print(f"repository cloned successfully to {clone_dir}")
        return nodes_dir
    
    except subprocess.CalledProcessError as e:
        print(f"error cloning repository: {e}")
        return None
    except Exception as e:
        print(f"unexpected error during git clone: {e}")
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

        # create temp files
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(response.content)
            temp_file_path = temp_file.name
        
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000, 2)

        # get size file
        content_size = os.path.getsize(temp_file_path)

        # delete tmp file
        os.unlink(temp_file_path)

        return {
            'status_code': response.status_code,
            'response_time_ms': response_time,
            'content_size_bytes': content_size,
            'url': url
        }
    
    # exceltions timeout 
    except requests.exceptions.Timeout:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        return {
            'status_code': 'TIMEOUT',
            'response_time_ms': 60000,
            'content_size_bytes': 0,
            'url': url
        }
    # exception connection error
    except requests.exceptions.ConnectionError:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        return {
            'status_code': 'CONNECTION_ERROR',
            'response_time_ms': 0,
            'content_size_bytes': 0,
            'url': url
        }
    # eception request exception
    except requests.exceptions.RequestException as e:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        return {
            'status_code': 'REQUEST_ERROR',
            'response_time_ms': 0,
            'content_size_bytes': 0,
            'error': str(e),
            'url': url
        }
    except Exception as e:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
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
        ZABBIX_SERVER = "127.0.0.1"
        ZABBIX_PORT = 10051

        # connecy to zbx srv
        sender = Sender(server=ZABBIX_SERVER, port=ZABBIX_PORT)

        print(f"\nsending data to zabbix for host: {hostname}")

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

            print(f"    {key}.status_code = {metrics['status_code']}")
            print(f"    {key}.response_time_ms = {metrics['response_time_ms']}")
            print(f"    {key}.content_size_bytes = {metrics['content_size_bytes']}")
            print(f"    {key}.transfer_rate = {transfer_rate} bytes/sec")

        # send via zbx srv
        print(f"\nsending {len(items)} items to zabbix")
        response = sender.send(items)
        print(f"{hostname}: {response.processed}/{response.total} items send successfully")

        if response.failed > 0:
            print(f"    failed: {response.failed} items")
            return False
        else:
            print(f"    all items sent successfully")
            return True
    except Exception as e:
        print(f"    error sending to zabbix: {e}")
        return False


def process_node(node_name, node_data):
    """process one node and return results"""
    results = {}
    endpoint = node_data.get('endpoint')

    if not endpoint:
        print(f"no endpoint found for node {node_name}")
        return results
    
    perf_checks = node_data.get('perfCheck', [])

    for check in perf_checks:
        webservice = check.get('webservice')
        scenario = check.get('scenario')

        if not webservice or not scenario:
            continue

        url = build_url(endpoint, webservice, check)

        print(f"testing {node_name}: {webservice}.{scenario}")
        result = make_request(url)

        # store result
        key = f"{webservice}.{scenario}"
        results[key] = {
            'status_code': result['status_code'],
            'response_time_ms': result['response_time_ms'],
            'content_size_bytes': result['content_size_bytes']
        }

        print(f" -> status: {result['status_code']}, time: {result['response_time_ms']}ms, size: {result['content_size_bytes']} bytes")
    
    return results

def main():
    # load all .yaml files
    nodes_dir = clone_repository()

    if not nodes_dir:
        print("failed to clone repository or find eida_nodes directory")
        return

    yaml_data = load_yaml_files(nodes_dir)
    
    if not yaml_data:
        print(f"no yaml files found in {nodes_dir}")
        return

    for node_name, node_data in yaml_data.items():
        print(f"\n{'='*50}")
        print(f"processing node: {node_name}")
        print(f"{'='*50}")

        results = process_node(node_name, node_data)

        if results:
            # send to zbx
            hostname = node_name.upper()
            if send_to_zabbix(hostname, results):
                print(f"{node_name}: perfCheck and zabbix sending completed")
            else:
                print(f"{node_name}: perfCheck completed but zabbix sending failed")
        else:
            print(f"no results for node {node_name}")

    print(f"\nall nodes processing completed")

if __name__ == "__main__":
    main()
