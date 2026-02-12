# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "argparse>=1.4.0",
#     "logging>=0.4.9.6",
#     "path>=17.1.1",
# ]
# ///

import argparse
import csv
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def csv_to_json(csv_file_path, json_file_path=None, encoding="utf-8"):
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
        json_file_path = csv_path.with_suffix(".json")

    data = []

    try:
        with Path(csv_file_path, encoding=encoding) as csv_file:
            csv_reader = csv.DictReader(csv_file)

            # read all rows into a list of dicts
            data = list(csv_reader)

        # write data to json file
        with Path(json_file_path, "w", encoding=encoding) as json_file:
            json.dump(data, json_file, indent=2, ensure_ascii=False)

        logger.info("conversion successful: %s -> %s", csv_file_path, json_file_path)
        logger.info("%d rows converted", len(data))

    except FileNotFoundError:
        logger.exception("file not found: %s", csv_file_path)
    except Exception:
        logger.exception("error during conversion")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description="converts a csv file to json")
    parser.add_argument("csv_file", help="path to the csv file to convert")
    parser.add_argument("-o", "--output", help="path to the output json file")
    parser.add_argument(
        "-e", "--encoding", default="utf-8", help="file encoding (default: utf-8)"
    )

    args = parser.parse_args()

    csv_to_json(args.csv_file, args.output, args.encoding)


if __name__ == "__main__":
    main()
