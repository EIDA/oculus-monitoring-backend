# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml",
# ]
# ///
import datetime
import json
import logging
import sys
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# expected number of command-line arguments (script name + input file)
EXPECTED_ARG_COUNT = 2

# allowed number of command-line arguments (script name + input file or with outpt file)
ALLOWED_ARG_COUNTS = (EXPECTED_ARG_COUNT, EXPECTED_ARG_COUNT + 1)

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return super().default(obj)

def flatten_yaml(data, parent_key="", sep="_"):
    """
    flattens a nested yaml/dict structure into a flat dictionarry
    args:
        data: the data structure to flatten
        parent_key: the parent key for nested structures
        sep: separator to use between keys
    returns:
        dict; flattened dictrionary
    """
    items = []
    if isinstance(data, dict):
        for k, v in data.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(flatten_yaml(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                for i, item in enumerate(v):
                    items.extend(flatten_yaml(item,
                                            f"{new_key}{sep}{i}",
                                            sep=sep).items())
            else:
                items.append((new_key, v))
    return dict(items)

def generate_lld(yaml_file):
    """
    generate ansible macros format output from a yaml file structure
    only processes specific sections; node, endpoint, routingFile, onlinecheck
    args:
        yaml_file (string): the path to the input yaml file
    """
    path = Path(yaml_file)
    with path.open() as yf:
        data = yaml.safe_load(yf)

    if not isinstance(data, dict):
        data = {}

    allowed_sections = ["node",
                        "endpoint",
                        "eidaRoutingFile",
                        "fdsnRoutingFile",
                        "onlineCheck"]
    filtered_data = {
        key: value
        for key, value in data.items()
        if key in allowed_sections
    }

    flattened_data = flatten_yaml(filtered_data)

    macros = []
    for key, value in flattened_data.items():
        macro_key = f"{{${key.upper()}}}"

        macro_entry = {
            "macro": macro_key,
            "value": str(value)
        }
        macros.append(macro_entry)

    # add CERT.WEBSITE.HOSTNAME for template web certificate
    endpoint_value = None
    for key, value in flattened_data.items():
        if key.upper() == "ENDPOINT":
            endpoint_value = str(value)
            break

    if endpoint_value:
        cert_macro = {
            "macro": "{$CERT.WEBSITE.HOSTNAME}",
            "value": endpoint_value
        }
        macros.append(cert_macro)

    return macros

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if len(sys.argv) not in ALLOWED_ARG_COUNTS:
        logger.error(
            "usage: python values_to_macros.py "
            "<input_yaml_file> [output_file]"
        )
        sys.exit(1)

    input_yaml_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) == EXPECTED_ARG_COUNT + 1 else None

    macros = generate_lld(input_yaml_file)

    out_yaml = yaml.safe_dump(macros, sort_keys=False)
    if output_file:
        Path(output_file).write_text(out_yaml)
        logger.info("Wrote %d macros to %s", len(macros), output_file)
    else:
        sys.stdout.write(out_yaml)
