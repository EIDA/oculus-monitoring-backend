#! /usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml",
# ]
# ///
import yaml
import json
import sys
import datetime

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return super().default(obj)
    
def flatten_yaml(data, parent_key='', sep='_'):
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
                    items.extend(flatten_yaml(item, f"{new_key}{sep}{i}", sep=sep).items())
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
    with open(yaml_file, 'r') as yf:
        data = yaml.load(yf, Loader=yaml.BaseLoader)

    allowed_sections = ['node', 'endpoint', 'routingFile', 'onlineCheck']
    filtered_data = {key: value for key, value in data.items() if key in allowed_sections}

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
        if key.upper() == 'ENDPOINT':
            endpoint_value = str(value)
            break
        
    if endpoint_value:
        cert_macro = {
            "macro": "{$CERT.WEBSITE.HOSTNAME}",
            "value": endpoint_value
        }
        macros.append(cert_macro)

    for macro in macros:
        print(f'- macro: "{macro["macro"]}"')
        print(f'  value: \'{macro["value"]}\'')


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python values_to_macros.py <input_yaml_file>")
        sys.exit(1)

    input_yaml_file = sys.argv[1]

    generate_lld(input_yaml_file)