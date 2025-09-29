import os
import yaml
import json
import time
import subprocess
import requests
from pathlib import Path
from urllib.parse import urlencode
import tempfile
from zabbix_utils import Sender

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
    base_url = f"https://{endpoint}/fdsnws/{webservice}/1/query"

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
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)

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
            'response_time_ms': 30000,
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
    # eception  request exception
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
    
def load_config():
    """load zbx config from config.yaml"""
    config_file = Path("config.yaml")
    if config_file.exists():
        with open(config_file, 'r') as f:
            return yaml.safe_load(f)
    return {}

def send_to_zabbix(zabbix_config, hostname, results):
    """send results output to zabbix server"""
    if not zabbix_config:
        print("no zabbix config found")
        return False
    
    try:
        sender = Sender(
            server=zabbix_config['server'],
            port=zabbix_config.get('port', 10051),
            timeout=zabbix_config.get('timeout', 10)
        )

        items = []

        for key, data in results.items():
            # send status code
            items.append({
                'host': hostname,
                'key': f'eida.perf[{key},status]',
                'value': str(data['status_code'])
            })
        
            # send response time
            items.append({
                'host': hostname,
                'key': f'eida.perf[{key},time]',
                'value': data['response_time_ms']
            })

            # send content size
            items.append({
                'host': hostname,
                'key': f'eida.perf[{key},size]',
                'value': data['content_size_bytes']
            })

        # send all items
        response = sender.send(items)

        print(f"zabbix send result: processed {response.processed}/{response.total} items")

        if response.failed > 0:
            print(f"failed items {response.failed}")
            for chunk in response.details:
                if chunk.failed > 0:
                    print(f"failed chunk: {chunk.info}")
        
        return response.failed == 0
    
    except Exception as e:
        print(f"error sending to zabbix: {e}")
        return False

def process_node(node_name, node_data, zabbix_config=None):
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

    # send to zabbix 
    if zabbix_config and results:
        if send_to_zabbix(zabbix_config, node_name, results):
            print(f"sucess send {len(results) * 3} items to zabbix for host '{node_name}'")
        else:
            print(f"fail to send data to zabbix for host '{node_name}'")
    
    return results

def main():
    config = load_config()
    zabbix_config = config.get('zabbix')

    nodes_dir = "../eida_nodes"
    yaml_data = load_yaml_files(nodes_dir)

    if not yaml_data:
        print(f"no YAML files found in {nodes_dir}")
        return
    
    results_dir = Path("performance_results")
    results_dir.mkdir(exist_ok=True)

    for node_name, node_data in yaml_data.items():
        print(f"\nprocessing node: {node_name}")

        results = process_node(node_name, node_data, zabbix_config)

        if results:
            # save results in json
            output_file = results_dir / f"{node_name}.json"
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)

            print(f"result saved to {output_file}")
        else:
            print(f"no result for node {node_name}")

if __name__ == "__main__":
    main()