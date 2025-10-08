import json
import re
import requests
import argparse
from datetime import datetime

ZABBIX_URL = "http://localhost:8888/api_jsonrpc.php"
ZABBIX_API_TOKEN = "9a195f4faab56c7ed9e0124efad34f33a6cd0291649f58c5ac9183af0e733c0b"

def get_zabbix_hosts():
    """get list og host names from zbx"""
    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "output": ["host"]
        },
        "auth": ZABBIX_API_TOKEN,
        "id": 1
    }

    try:
        response = requests.post(ZABBIX_URL, json=payload, headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        result = response.json()

        if 'result' in result:
            # convert host name to lowercase for comparison
            return [host['host'].lower() for host in result['result']]
        else:
            print(f"error getting hosts: {result.get('error', 'unknow error')}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"error connecting to zbx {e}")
        return []

def send_to_zabbix(data_points, dry_run=False):
    """send history data to zabbux using history?.push API"""
    # convert tumestamp to unix timestamp for zbx
    zabbix_data = []

    for item in data_points:
        timestamp = item["timestamp"]
        # convert
        dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
        unix_timestamp = int(dt.timestamp())

        # user uppercase eida_node for zbx host
        eida_node = item["eida_node"].upper()

        # create data points for metrics
        for key, value in item.items():
            if key not in ["eida_node", "timestamp"]:
                zabbix_data.append({
                    "host": eida_node,
                    "key": key,
                    "value": str(value),
                    "clock": unix_timestamp
                })

    if not zabbix_data:
        print("no data to send to zabbix")
        return True

    if dry_run:
        print(f"[dry-run] would send {len(zabbix_data)} data points to zbx")
        print("[dry-run] sample data points:")
        for i, point in enumerate(zabbix_data[:5]):  # show firsts 5 points
            print(f" {i+1}. host: {point['host']}, key {point['key']}, value: {point['value']}, timestamp: {point['clock']}")
        if len(zabbix_data) > 5:
            print(f" ... and {len(zabbix_data) - 5} more data points")
        return True
    
    # split chunchks of 1000 zbx iteùs (limit)
    chunk_size = 1000
    total_chunks = (len(zabbix_data) + chunk_size - 1) // chunk_size

    for i in range(0, len(zabbix_data), chunk_size):
        chunk = zabbix_data[i:i + chunk_size]
        chunk_num = i // chunk_size + 1

        payload = {
            "jsonrpc": "2.0",
            "method": "history.push",
            "params": chunk,
            "auth": ZABBIX_API_TOKEN,
            "id": chunk_num
        }

        try:
            response = requests.post(ZABBIX_URL, json=payload, headers={'Content-Type': 'application/json'})
            response.raise_for_status()
            result = response.json()

            if 'result' in result:
                print(f"successfully sent chunk {chunk_num}/{total_chunks} ({len(chunk)} items)")
            else:
                print(f"error sending chunk {chunk_num}: {result.get('error', 'unknow error')}")
                return False
        
        except requests.exceptions.RequestException as e:
            print(f"error senfing chunk {chunk_num} to zbx: {e}")
            return False
    
    print(f"successfully snt all {len(zabbix_data)} data points to zbx")
    return True

def send_file_to_zbx(file_path, dry_run=False):
    """send transfomed data from file to zbx"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"loaded {len(data)} records from {file_path}")
        return send_to_zabbix(data, dry_run)
    
    except FileNotFoundError:
        print(f"error: file '{file_path}' not found")
        return False
    except json.JSONDecodeError as e:
        print(f"error: invalid json in file - {e}")
        return False
    
def parse_duration_to_ms(duration_str):
    """convert duration string from format "HH:MM:SS.microsecnodes" to milliseconds"""
    #parse the duaratio string format : "00:00:01.351381"
    match = re.match(r'(\d+):(\d+):(\d+)\(\d+)', duration_str)
    if match:
        hours, minutes, seconds, microseconds = map(int, match.groups())
        total_ms = (hours * 3600 + minutes * 60 + seconds) * 1000 + microseconds // 1000
        return total_ms
    return 0

def parse_duration_to_seconds(duration_str):
    """convert duration string fril "HH:MM:SS.microsecon" to seconds"""
    # parse the duration string format: "00:00:01.351381"
    match = re.match(r'(\d+):(\d+):(\d+)\.(\d+)', duration_str)
    if match:
        hours, minutes, seconds, microseconds = map(int, match.groups())
        total_seconds = hours * 3600 + minutes * 60 + seconds + microseconds / 1000000
        return total_seconds
    return 0

def calculate_transfer_rate(response_length, request_duration):
    """calculate transfer rate bytes/s"""
    try:
        length = int(response_length)
        duration_seconds = parse_duration_to_seconds(request_duration)

        if duration_seconds > 0:
            return round(length / duration_seconds, 2)
        else:
            return 0
    except (ValueError, ZeroDivisionError):
        return 0
    
def transform_testid_and_extract_host(testid):
    """transform testid according to rules and extract host name:
    - staxmlresp or statxt -> ignore (return none)
    - staxml -> station
    - avail -> availability
    - 1minAM or 1minPM -> dataselect
    - remove "1min and "1day" from result
    - replace "resif" to "eposfr"
    - remove "text"
    - extract host name (second part) and rmit from testid"""
    # check longer patterns fist to apartial matchs
    if testid.startswith("staxmlresp") or testid.startswith("statxt"):
        return None, None
    elif testid.startswith('staxml'):
        result = "station" + testid[6:] #replace first + chars
    elif testid.startswith("avail"):
        result = "availability" + testid[5:]
    elif testid.startswith("1minAM"):
        result = "dataselect" + testid[6:]
    elif testid.startswith("1minPM"):
        result = "dataselect" + testid[6:]
    else:
        result = testid
    
    # clean up patterns
    result = result.replace("-1min-", "-")
    result = result.replace("-1day-", "-")
    result = result.replace("resif", "eposfr")
    result = result.replace("-text-", "-")
    if result.endwith("-text"):
        result = result[:-5]
    
    # split and extrazct host
    parts = result.split('-')
    if len(parts) >= 3:
        service = parts[0]
        host = parts[1]
        streams = '-'.join(parts[2:])
        final_testid = f"{service}.{streams.replace('-', '.')}"
        return final_testid, host
    elif len(parts) >= 2:
        # failback for cases with only 2 parts
        host = parts = parts[1]
        final_testid = parts[0]
        return final_testid, host
    
    return result.replace('-', '.'), None

def filter_testid_by_host(eida_node, zabbix_hosts):
    """filter testid based on zbx hosts, keep only if eida_nodes match a zbx host"""
    if eida_node and eida_node.lower() in zabbix_hosts:
        return True
    return False

def transform_test_results(input_file, output_file):
    """transform test results json file with new dield names and convert duration to ms"""
    try:
        # get zbx hosts
        print("connecting to zbx server")
        zabbix_hosts = get_zabbix_hosts()

        if not zabbix_hosts:
            print("failed to get hosts from zabbix, processing shitout host filtering")
        else:
            print(f"retrived {len(zabbix_hosts)} hosts from zabbix")

        # read the input from json files
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        print(f"loaded {len(data)} records from {input_file}")

        # transform test result
        transformed_data = []
        filtered_count = 0
        ignored_count = 0
        filtered_items = []
        ignored_items = []

        for item in data:
            # skip incomplete items
            if not all(key in item for key in ["testid", "timestamp", "requestduration", "returncode", "responselength"]):
                continue

            # transform testid and extract host
            new_testid, eida_node = transform_testid_and_extract_host(item["testid"])

            # skip item ignored (statxt, staxmlresp...)
            if new_testid is None:
                ignored_count += 1
                ignored_items.append({
                    "original_testid": item["testid"],
                    "reason": "ignored rule (statxt/staxmlresp)"
                })
                continue

            # fiilter by zbx host if available
            if zabbix_hosts and eida_node:
                if not filter_testid_by_host(eida_node, zabbix_hosts):
                    filtered_count += 1
                    filtered_items.append({
                        "original_testid": item["testid"],
                        "extracted_host": eida_node,
                        "reason": "host not found in zabbix"
                    })
                    continue
            
            response_time = parse_duration_to_ms(item["requestduration"])
            status_code = int(item["returncode"]) # convert to int
            content_size = int(item["responselength"])
            transfer_rate = calculate_transfer_rate(item["responselength"], item["requestduration"])

            transformed_item = {
                "eida_node": eida_node.upper() if eida_node else None,
                "timestamp": item["timestamp"],
                f"{new_testid}.response_time_ms": response_time,
                f"{new_testid}.status_code": status_code,
                f"{new_testid}.content_size_bytes": content_size,
                f"{new_testid}.transfer_rate": transfer_rate
            }
            transformed_data.append(transformed_item)

        # display filtered and ignored items
        if filtered_items:
            print(f"\n filtered out items ({len(filtered_items)}):")
            for item in filtered_items:
                print(f"    - {item['original_testid']} (host: {item['extracted_host']}) - {item['reason']}")

        if ignored_items:
            print(f"\nignored items ({len(ignored_items)}):")
            for item in ignored_items:
                print(f"    - {item['original_testid']} - {item['reason']}")

        # write transformed data to to output file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(transformed_data, f, indent=2, ensure_ascii=False)

        print(f"\ntransformation completed successfully")
        print(f"    input file: {input_file}")
        print(f"    output file: {output_file}")
        print(f"    records processed: {len(transformed_data)}")
        print(f"    records filtered: {filtered_count}")
        print(f"    records ignored: {ignored_count}")

        return True
    
    except FileNotFoundError:
        print(f"error: input file '{input_file}' not found")
        return False
    except json.JSONDecodeError as e:
        print(f"error: invlid json in input file - {e}")
        return False
    except Exception as e:
        print(f"error {e}")
        return False
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='transform perfcheck results and send to zabbix')
    parser.add_argument('--input', '-i', default='pc_tests_results_clean.json',
                        help='input json file default: pc_tests_results_clean.json')
    parser.add_argument('--output', '-o', default='pc_tests_results_transformed.json',
                        help='output json file (default: pc_tests_results_transformed.json)')
    parser.add_argument('--send_file', '-s',
                        help='send specific transformed file to zabbix')
    parser.add_argument('--dry-run', action='store_true',
                        help='dry run mode - show what would be done without actually doing it')
    
    args = parser.parse_args()

    if args.send_file:
        #send specific file to zbx
        print(f"sending file {args.send_file} to zabbix")
        success = send_file_to_zbx(args.send_file, dry_run=args.dry_run)
    else:
        # transform data only
        print("transforming data")
        success = transform_test_results(args.input, args.output)

    if not success:
        exit(1)