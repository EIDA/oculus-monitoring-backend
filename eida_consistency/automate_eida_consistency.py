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
            check=True
            capture_output=True
            text=True
        )

        log_and_print(f"command completed successfullt")
        log_and_print(f"stdout: {result.stdout}")

        return True