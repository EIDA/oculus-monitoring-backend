import yaml
from urllib.parse import parse_qs
import argparse
from collections import OrderedDict

# Configure YAML to handle OrderedDict properly
def represent_ordereddict(dumper, data):
    return dumper.represent_dict(data.items())

yaml.add_representer(OrderedDict, represent_ordereddict)

def query_to_yaml(query):
    # Extract the query parameters
    query_params = parse_qs(query)
    # Convert lists to single values if they contain only one item
    query_params = {key: value[0] if len(value) == 1 else value for key, value in query_params.items()}
    
    # Map shortname
    key_mapping = {
        "network": "net",
        "station": "sta",
        "channel": "cha",
        "starttime": "start",
        "endtime": "end",
        "location": "loc"
    }
    # Replace keys based on the mapping
    query_params = {key_mapping.get(key, key): value for key, value in query_params.items()}
    
    # Ensure empty fields are represented as empty strings
    for key in ["net", "sta", "loc", "cha", "start", "end"]:
        if key not in query_params:
            query_params[key] = ""

    # Reorder keys to match the desired order
    ordered_keys = ["net", "sta", "loc", "cha", "start", "end"]
    ordered_query_params = OrderedDict((key, query_params[key]) for key in ordered_keys if key in query_params)
    
    return ordered_query_params

if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Convert query parameters to YAML format.")
    parser.add_argument("-f", "--file", help="Path to a file containing multiple query strings, one per line.")
    
    # Parse arguments
    args = parser.parse_args()
    
    section_order = ["9streams", "54streams", "320streams", "1stream20days"]
    
    if args.file:
        # Read queries from the file
        with open(args.file, "r") as file:
            lines = file.readlines()
            output = OrderedDict()
            for section, line in zip(section_order, lines):
                line = line.strip()
                if line:  # Skip empty lines
                    output[section] = query_to_yaml(line)
            
            # Convert the final output to YAML
            yaml_output = yaml.dump(output, default_flow_style=False, allow_unicode=True)
            print(yaml_output)
    else:
        print("Error: You must provide a file containing queries.")