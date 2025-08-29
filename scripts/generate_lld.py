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
        return json.JSONEncoder.default(self,    obj)

def flatten_yaml(data, parent_key='', sep='_'):
    """
    Recursively flattens a nested dictionayr, prefixing keys with a parent key and convetring them to uppercase
    
    Args :
        data (dict ) : The dictionary to flatten
        parent_key (str): The base key to prefix
        sep (str) : The separator between keys
    
    Returns:
        dict : A flattened dictionary with prefixe keys
    """
    items = []
    for key, value in data.items():
        new_key = f"{parent_key}{sep}{key}".upper() if parent_key else key.upper()
        if isinstance(value, dict):
            items.extend(flatten_yaml(value, new_key, sep=sep).items())
        else:
            items.append((new_key, value))
    return dict(items)

def generate_lld(yaml_file):
    """
    Generates a LLD JSON output from a YAML file struture and print in  the console
    
    Args:
        yaml_file (str): The path to the input YAML fille
    """
    # Load the YAML file
    with open(yaml_file, 'r') as yf:
        data = yaml.load(yf,Loader=yaml.BaseLoader)

    # Flatten the YAML data
    flattened_data = flatten_yaml(data)
    
    # Create the LLD data with the desired format
    lld_data = {f"{{#{key}}}": f"{value}" for key, value in flattened_data.items()}
    
    # Print the LLD data as JSON to the console
    print(json.dumps([lld_data], indent=2, cls=DateTimeEncoder))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python generate_lld.py <input_yaml_file>")
        sys.exit(1)
    
    input_yaml_file = sys.argv[1]
    
    generate_lld(input_yaml_file)