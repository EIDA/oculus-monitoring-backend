import yaml
import json
import sys

def flatten_yaml(data, parent_key='EIDA', sep='_'):
    """
    Recursively flatens a nested dictionary, prefixing keys with 'EIDA_' and convertingg them to uprrcase
    
    Args:
        data (dict) : The dictionary to flatten
        parent_key (str) : The base key to prefix
        sep (str) : The separator between keys
    
    Returns:
        dict : A flattened dictionary with prefixed keys
    """
    items = []
    for key, value in data.items():
        new_key = f"{parent_key}{sep}{key}".upper()
        if isinstance(value, dict):
            items.extend(flatten_yaml(value, new_key, sep=sep).items())
        else:
            items.append((new_key, value))
    return dict(items)

def generate_lld(yaml_file):
    """
    Generates an LLD JSON output from a YAML file structure and prints it to the console
    
    Args:
        yaml_file (str): The path to the input YAML file
    """
    # Load the YAML file
    with open(yaml_file, 'r') as yf:
        data = yaml.safe_load(yf)
    
    # Flatten the YAML data
    flattened_data = flatten_yaml(data)
    
    # Create the LLD data with the desired format
    lld_data = {f"{{#{key}}}": "{{ .Values." + key.lower().replace('eida_', '') + " }}" for key in flattened_data.keys()}
    
    # Print the LLD data as JSON to the console
    print(json.dumps([lld_data], indent=4))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python generate_lld_print.py <input_yaml_file>")
        sys.exit(1)
    
    input_yaml_file = sys.argv[1]
    
    generate_lld(input_yaml_file)
