import os
import subprocess
import logging
import json
from pathlib import Path
from zabbix_utils import Sender, ItemValue

# config logging
logging.basicConfig(
    level=logging.INFO,
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

def run_eida_consistency(node, epochs=10, duration=600):
    """run eida-consistency command"""
    try:
        cmd = [
            'eida-consistency',
            'consistency',
            '--node', node,
            '--epochs', str(epochs),
            '--duration', str(duration)
        ]

        log_and_print(f"running command {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )

        log_and_print(f"command completed successfullt")
        log_and_print(f"stdout: {result.stdout}")

        return True

    except subprocess.CalledProcessError as e:
        log_and_print(f"error running eida-consistency: {e}", logging.ERROR)
        log_and_print(f"stderr: {e.stderr}", logging.ERROR)
        return False
    except Exception as e:
        log_and_print(f"unexpected error: {e}", logging.ERROR)
        return False

def get_latest_json_file(reports_dir='reports'):
    """get the latest JSON file fromreports directory"""
    try:
        reports_path = Path(reports_dir)

        if not reports_path.exists():
            log_and_print(f"reports directory not found {reports_dir}", logging.ERROR)
            return None

        json_files = list(reports_path.glob('*.json'))

        if not json_files:
            log_and_print("no JSON files found in reports directory", logging.ERROR)
            return None

        # get the most recent file
        latest_file = max(json_files, key=lambda f: f.stat().st_mtime)

        log_and_print(f"latest JSON file: {latest_file}")
        return latest_file

    except Exception as e:
        log_and_print(f"error finding latest JSON file: {e}", logging.ERROR)
        return None

def send_to_zabbix(hostname, json_file_path):
    """send JSON report to zbx"""
    try:
        # zbx srv config
        ZABBIX_SERVER = os.getenv('ZABBIX_SERVER')
        ZABBIX_PORT = 10051

        if not ZABBIX_SERVER:
            log_and_print("ZABBIX_SERVER environement variable not set", logging.ERROR)
            return False

        # read JSON file
        with open(json_file_path, 'r') as f:
            json_content = json.load(f)

        # convert  JSON to string for sending
        json_string = json.dumps(json_content)

        # connect to zbx srv
        sender = Sender(server=ZABBIX_SERVER, port=ZABBIX_PORT)

        log_and_print(f"sending data to zabbix fot host: {hostname}")

        # create item
        item = ItemValue(hostname, 'report.json', json_string)

        # send via zbx srv
        response = sender.send([item])

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

def main():
    node ='RESIF'
    epochs = 10
    duration = 600

    log_and_print(f"{'='*50}")
    log_and_print(f"starting EIDA consistency check for node: {node}")
    log_and_print(f"{'='*50}")

    # run eida-consistency
    if not run_eida_consistency(node, epochs, duration):
        log_and_print("eida-consistency command failed", logging.ERROR)
        return

    # get latest JSON file
    json_file = get_latest_json_file()

    if not json_file:
        log_and_print("no JSON file to send", logging.ERROR)
        return

    # send to zabbix
    hostname = node.upper()
    if send_to_zabbix(hostname, json_file):
        log_and_print(f"process completed successfully for {node}")
    else:
        log_and_print(f"failed to send report to zabbix for {node}", logging.ERROR)

if __name__ == "__main__":
    main()