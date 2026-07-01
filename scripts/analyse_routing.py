# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "argparse>=1.4.0",
#     "counter>=1.0.0",
#     "logging>=0.4.9.6",
#     "path>=17.1.1",
# ]
# ///

import argparse
import csv
import logging
from collections import Counter
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description="Analyse Zabbix problem host frequency.")
parser.add_argument(
    "csv_path",
    type=Path,
    help="path to the zbx_problems_export.csv file",
)
args = parser.parse_args()

host_counter = Counter()

with args.csv_path.open("r", encoding="utf-8") as file:
    reader = csv.DictReader(file)
    for row in reader:
        host = row["Host"]
        host_counter[host] += 1

sorted_hosts = host_counter.most_common()

logger.info("hosts by frequency (most cited to least cited):\n")
logger.info("%-15s %20s", "host", "number of occurrences")
logger.info("-" * 40)

for host, count in sorted_hosts:
    logger.info("%-15s %20d", host, count)

logger.info("total unique hosts: %d", len(host_counter))
logger.info("total problems: %d", sum(host_counter.values()))
