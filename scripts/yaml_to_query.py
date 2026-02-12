# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "argparse>=1.4.0",
#     "logging>=0.4.9.6",
#     "path>=17.1.1",
#     "pyyaml>=6.0.3",
# ]
# ///

import argparse
import logging
from pathlib import Path
from urllib.parse import unquote, urlencode

import yaml

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def load_eposfr_config(file_path):
    """load configuration from yaml file"""
    with Path(file_path).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def clean_value(value):
    """remove quotes from string values"""
    if isinstance(value, str):
        return value.replace('"', "").replace("'", "")
    return value


def build_query_url(base_url, webservice, params):
    """build query url with parameters"""
    # mapping webservices to their endpoints with correct paths
    if webservice == "wfcatalog":
        full_base_url = f"{base_url}eidaws/wfcatalog/1/query"
    elif webservice in ["dataselect", "availability", "station"]:
        full_base_url = f"{base_url}fdsnws/{webservice}/1/query"
    else:
        # fallback for other webservices
        full_base_url = f"{base_url}fdsnws/{webservice}/1/query"

    # query parameters
    query_params = {}

    if "net" in params:
        query_params["network"] = clean_value(params["net"])
    if "sta" in params:
        query_params["station"] = clean_value(params["sta"])
    if "loc" in params:
        query_params["location"] = clean_value(params["loc"])
    if "cha" in params:
        query_params["channel"] = clean_value(params["cha"])
    if "start" in params:
        query_params["starttime"] = clean_value(params["start"])
    if "end" in params:
        query_params["endtime"] = clean_value(params["end"])

    # build complete url
    if query_params:
        url = f"{full_base_url}?{urlencode(query_params)}"
        # decode url to remove % encoding
        url = unquote(url)
    else:
        url = full_base_url

    return url


def generate_urls_from_config(file_path):
    """generate all query urls from yaml file"""
    config = load_eposfr_config(file_path)

    base_url = f"https://{config['endpoint']}/"
    perf_checks = config.get("perfCheck", [])

    urls_by_scenario = {}

    for check in perf_checks:
        webservice = check.get("webservice")
        scenario = check.get("scenario")

        if not webservice or not scenario:
            continue

        # build url for this check
        url = build_query_url(base_url, webservice, check)

        # organize by scenario
        scenario_key = f"{webservice}_{scenario}"
        if scenario_key not in urls_by_scenario:
            urls_by_scenario[scenario_key] = []

        urls_by_scenario[scenario_key].append(
            {
                "url": url,
                "webservice": webservice,
                "scenario": scenario,
                "params": {
                    k: v
                    for k, v in check.items()
                    if k not in ["webservice", "scenario"]
                },
            }
        )

    return urls_by_scenario


def print_urls(urls_by_scenario):
    """display urls organized by scenario"""
    for scenario_key, urls in urls_by_scenario.items():
        logger.info("\n=== %s ===", scenario_key)
        for i, url_info in enumerate(urls, 1):
            logger.info("%d. %s", i, url_info["url"])
            logger.info("   webservice: %s", url_info["webservice"])
            logger.info("   scenario: %s", url_info["scenario"])
            logger.info("   params: %s", url_info["params"])
            logger.info("")


def save_urls_only(urls_by_scenario, output_file):
    """save only urls to file"""
    output_path = Path(output_file)
    with output_path.open("w", encoding="utf-8") as f:
        for urls in urls_by_scenario.values():
            f.writelines(f"{url_info['url']}\n" for url_info in urls)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="generate query urls from yaml file")
    parser.add_argument("yaml_file", help="input yaml file (ex: eposfr.yaml)")
    parser.add_argument("--output", "-o", help="output file to save urls")
    parser.add_argument("--scenario", "-s", help="filter by specific scenario")

    args = parser.parse_args()

    try:
        # generate urls
        urls_by_scenario = generate_urls_from_config(args.yaml_file)

        # filter by scenario if specified
        if args.scenario:
            filtered_urls = {
                k: v
                for k, v in urls_by_scenario.items()
                if args.scenario.lower() in k.lower()
            }
            urls_by_scenario = filtered_urls

        # display urls (detailed)
        print_urls(urls_by_scenario)

        # save only urls if requested
        if args.output:
            save_urls_only(urls_by_scenario, args.output)
            logger.info("\nurls saved to %s", args.output)

        logger.info("\ntotal: %d urls generated",
                    sum(len(urls) for urls in urls_by_scenario.values()))
        logger.info("scenarios: %d", len(urls_by_scenario))

    except FileNotFoundError:
        logger.exception("error: file '%s' not found", args.yaml_file)
    except yaml.YAMLError:
        logger.exception("error: invalid yaml format - %s")
    except Exception:
        logger.exception("error: %s")
