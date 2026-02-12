# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "logging>=0.4.9.6",
#     "pandas>=3.0.0",
#     "path>=17.1.1",
# ]
# ///

import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REQUIRED_ARG_COUNT = 2

# check files
if len(sys.argv) < REQUIRED_ARG_COUNT:
    logger.error("Usage: python csv_delete_last_columns.py <file.csv>")
    sys.exit(1)

input_file = sys.argv[1]

# check if file exists
if not Path(input_file).exists():
    logger.error("Error: file %s doesn't exist.", input_file)
    sys.exit(1)

try:
    # read csv file preserving NULL values as strings
    df = pd.read_csv(
        input_file, quoting=3, escapechar="\\", keep_default_na=False, na_values=[]
    )

    # check if file is empty
    if df.empty:
        logger.error("Error: CSV file is empty.")
        sys.exit(1)

    # check if file has columns
    if df.shape[1] < 1:
        logger.error("Error: CSV has no columns.")
        sys.exit(1)

    logger.info("Original file: %d rows, %d columns", df.shape[0], df.shape[1])
    logger.info("\nColumns available:")

    # show all columns with index
    for i, column in enumerate(df.columns):
        logger.info("%d: %s", i, column)

    # ask to  user which column to delete
    while True:
        try:
            choice = input(
                f"\nWhich column to delete ? (0-{len(df.columns) - 1}) or 'q' for quit:"
            )

            if choice.lower() == "q":
                logger.info("Canceled.")
                sys.exit(0)

            column_index = int(choice)

            if 0 <= column_index < len(df.columns):
                column_to_delete = df.columns[column_index]
                logger.info("Delete the column: '%s'", column_to_delete)

                confirm = input("Confirm ? (y/n): ")
                if confirm.lower() in ["y", "yes", "o", "oui"]:
                    # Delete selected column
                    df = df.drop(columns=[column_to_delete])
                    break
                else:
                    logger.info("Deletion canceled.")
                    continue
            else:
                logger.error("Error: enter a number between 0 and %d",
                            len(df.columns) - 1)
        except ValueError:
            logger.exception("Error: enter a valid number or 'q' for quit")

    # save preserving NULL values and original format
    output_file = input_file.replace(".csv", "_clean.csv")
    df.to_csv(output_file, index=False, quoting=3, escapechar="\\")

    logger.info("Column '%s' deleted — file saved here: %s",
                column_to_delete,
                output_file)
    logger.info("New file: %d rows, %d columns",
                df.shape[0],
                df.shape[1])

except pd.errors.EmptyDataError:
    logger.exception("Error: CSV file is empty or badly formatted.")
except KeyboardInterrupt:
    logger.warning("Operation canceled.")
except Exception:
    logger.exception("Error during processing: %s")
