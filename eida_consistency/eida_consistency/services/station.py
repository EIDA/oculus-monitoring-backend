"""EIDA **station** web-service (text format only).

Workflow:
1. Fetch all networks (format=text)
2. Fetch all stations per network (format=text, parallel)
3. Pick random station subsets (controlled by station_multiplier × epochs)
4. Fetch channels for those stations (format=text, parallel)

Return flat candidates:
{network, station, channel, starttime[, endtime][, location]}
"""

import logging
import random
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from eida_consistency.utils.constants import USER_AGENT


def _fetch_text(url: str, timeout: int = 60) -> list[str]:
    """Fetch a station service URL in text format and return non-comment lines."""
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        lines = resp.text.strip().splitlines()
        return [line for line in lines if line and not line.startswith("#")]
    except Exception as e:
        logging.debug(f"[station] Fetch text failed {url}: {e}")
        return []


def fetch_candidates(base_url: str, max_candidates: int = 30, max_workers: int = 10):
    """
    Fetch random NSLC candidates for testing.

    Parameters
    ----------
    base_url : str
        Node base URL (e.g. https://webservices.ingv.it/fdsnws/)
    max_candidates : int
        Total number of NSLC candidates to return (station_multiplier × epochs).
    max_workers : int
        Thread pool size for parallel fetching.

    Returns
    -------
    list of dict
        Flat NSLC candidates
    """
    # --- Step 1: Fetch networks ---
    url = f"{base_url}station/1/query?level=network&format=text&includerestricted=false&nodata=404"
    net_lines = _fetch_text(url)
    networks = [line.split("|", 1)[0] for line in net_lines if "|" in line]
    if not networks:
        logging.warning("No networks found.")
        return []

    # --- Step 2: Fetch stations per network (parallel) ---
    sta_pairs = []
    station_urls = [
        f"{base_url}station/1/query?network={net}&level=station&format=text&includerestricted=false&nodata=404"
        for net in networks
    ]

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_fetch_text, u): u for u in station_urls}
        for fut in as_completed(futures):
            lines = fut.result()
            for line in lines:
                parts = line.split("|")
                if len(parts) >= 2:
                    net, sta = parts[0], parts[1]
                    sta_pairs.append((net, sta))

    if not sta_pairs:
        logging.warning("No stations found.")
        return []

    # --- Step 3: Pick random stations ---
    random.shuffle(sta_pairs)
    selected_sta = sta_pairs[: max_candidates]

    # --- Step 4: Fetch channels for selected stations (parallel) ---
    candidates = []
    chan_urls = [
        f"{base_url}station/1/query?network={net}&station={sta}"
        f"&level=channel&format=text&includerestricted=false&nodata=404"
        for net, sta in selected_sta
    ]

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_fetch_text, u): u for u in chan_urls}
        for fut in as_completed(futures):
            lines = fut.result()
            for line in lines:
                parts = line.split("|")
                # Expected: Network|Station|Location|Channel|...|StartTime|EndTime
                if len(parts) < 16:
                    continue
                net_code, sta_code, loc_code, cha_code = parts[0], parts[1], parts[2], parts[3]
                start, end = parts[-2], parts[-1]

                if not (net_code and sta_code and cha_code and start):
                    continue

                entry = {
                    "network": net_code,
                    "station": sta_code,
                    "channel": cha_code,
                    "starttime": start,
                }
                if end and end.strip():
                    entry["endtime"] = end
                if loc_code and loc_code.strip():
                    entry["location"] = loc_code

                candidates.append(entry)

    if not candidates:
        logging.warning("No channel candidates found.")

    return candidates
