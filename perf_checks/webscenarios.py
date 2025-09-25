import os
import yaml
import json
import time
import subprocess
import requests
from pathlib import Path
from urllib.parse import urlencode
import tempfile

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
    nodes_dir = "../eida_nodes"
    yaml_data = load_yaml_files(nodes_dir)

    if not yaml_data:
        print(f"no YAML files found in {nodes_dir}")
        return
    
    results_dir = Path("performance_results")
    results_dir.mkdir(exist_ok=True)

    for node_name, node_data in yaml_data.items():
        print(f"\nprocessing node: {node_name}")

        results = process_node(node_name, node_data)

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