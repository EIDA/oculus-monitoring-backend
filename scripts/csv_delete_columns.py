import pandas as pd
import sys
import os

# check files
if len(sys.argv) < 2:
    print("Usage: python csv_delete_last_columns.py <file.csv>")
    sys.exit(1)

input_file = sys.argv[1]

# check if file existe
if not os.path.exists(input_file):
    print(f"Error: file {input_file} dosen't exist.")
    sys.exit(1)

try:
    # read csv file preserving NULL values as strings
    df = pd.read_csv(input_file, quoting=3, escapechar='\\', keep_default_na=False, na_values=[])
    
    # check if file is empty
    if df.empty:
        print("Error: file CSV is empty.")
        sys.exit(1)
    
    # check if file have columns
    if df.shape[1] < 1:
        print("Error: file has no column.")
        sys.exit(1)
    
    print(f"Original file: {df.shape[0]} lignes, {df.shape[1]} columns")
    print("\nColumns available:")
    
    # show all columns with index
    for i, column in enumerate(df.columns):
        print(f"{i}: {column}")
    
    # ask to  user which column to delete
    while True:
        try:
            choice = input(f"\nWhich column to delete ? (0-{len(df.columns)-1}) or 'q' for quit: ")
            
            if choice.lower() == 'q':
                print("Canceled.")
                sys.exit(0)
            
            column_index = int(choice)
            
            if 0 <= column_index < len(df.columns):
                column_to_delete = df.columns[column_index]
                print(f"Delete the column: '{column_to_delete}'")
                
                confirm = input("Confirm ? (y/n): ")
                if confirm.lower() in ['y', 'yes', 'o', 'oui']:
                    # Delete selected column
                    df = df.drop(columns=[column_to_delete])
                    break
                else:
                    print("Deletion canceled.")
                    continue
            else:
                print(f"Error: enter a number between 0 and {len(df.columns)-1}")
        except ValueError:
            print("Error: enter a valid number or 'q' for quit")
    
    # save preserving NULL values and original format
    output_file = input_file.replace('.csv', '_clean.csv')
    df.to_csv(output_file, index=False, quoting=3, escapechar='\\')
    
    print(f"\nColumn '{column_to_delete}' deleted ! File save here : {output_file}")
    print(f"New file : {df.shape[0]} lignes, {df.shape[1]} columns")

except pd.errors.EmptyDataError:
    print("Erroe: CSV file is empty or bad formated.")
except KeyboardInterrupt:
    print("\Operation canceled.")
except Exception as e:
    print(f"Error during processing: {str(e)}")