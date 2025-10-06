import csv
import json
import argparse
from pathlib import Path

def csv_to_json(csv_file_path, json_file_path=None, encoding='utf-8'):
    """
    converts a csv file to json format
    
    args:
        csv_file_path (str): path to the csv file
        json_file_path (str, optional): path to the output json file
        encoding (str): file encoding (default 'utf-8')
    """
    
    # if no output file is specified, use the same name with .json extension
    if json_file_path is None:
        csv_path = Path(csv_file_path)
        json_file_path = csv_path.with_suffix('.json')
    
    data = []
    
    try:
        with open(csv_file_path, 'r', encoding=encoding) as csv_file:
            csv_reader = csv.DictReader(csv_file)
            
            # convert each row to dictionary
            for row in csv_reader:
                data.append(row)
        
        # write data to json file
        with open(json_file_path, 'w', encoding=encoding) as json_file:
            json.dump(data, json_file, indent=2, ensure_ascii=False)
        
        print(f"conversion successful: {csv_file_path} -> {json_file_path}")
        print(f"{len(data)} rows converted")
        
    except FileNotFoundError:
        print(f"error: file {csv_file_path} does not exist")
    except Exception as e:
        print(f"error during conversion: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='converts a csv file to json')
    parser.add_argument('csv_file', help='path to the csv file to convert')
    parser.add_argument('-o', '--output', help='path to the output json file')
    parser.add_argument('-e', '--encoding', default='utf-8', help='file encoding (default: utf-8)')
    
    args = parser.parse_args()
    
    csv_to_json(args.csv_file, args.output, args.encoding)

if __name__ == "__main__":
    main()