#! /bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pyyaml",
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
    Flattens a nested YAML/dict structure into a flat dictionary.
    
    Args:
        data: The data structure to flatten
        parent_key: The parent key for nested structures
        sep: The separator to use between keys
    
    Returns:
        dict: Flattened dictionary
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
    Generates Ansible macros format output from a YAML file structure
    Only processes specific sections: node, endpoint, routingFile, onlineCheck
    
    Args:
        yaml_file (str): The path to the input YAML file
    """
    # load the YAML file
    with open(yaml_file, 'r') as yf:
        data = yaml.load(yf, Loader=yaml.BaseLoader)

    # Filter data to include only specified sections
    allowed_sections = ['node', 'endpoint', 'routingFile', 'onlineCheck']
    filtered_data = {key: value for key, value in data.items() if key in allowed_sections}
    
    flattened_data = flatten_yaml(filtered_data)
    
    # generate Ansible macros format
    macros = []
    for key, value in flattened_data.items():
        macro_key = f"{{${key.upper()}}}"
        
        macro_entry = {
            "macro": macro_key,
            "value": str(value)
        }
        macros.append(macro_entry)
    
    # add CERT.WEBSITE.HOSTNAME for Template Web Certificate
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
        print("Usage: python values_to_macros.py <input_yaml_file>")
        sys.exit(1)
    
    input_yaml_file = sys.argv[1]
    
    generate_lld(input_yaml_file)