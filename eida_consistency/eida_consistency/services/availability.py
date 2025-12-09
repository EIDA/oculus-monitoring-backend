"""EIDA availability (text spans).

Supports payload in text format, multiple variants:
- 8 fields: Net Sta Loc Cha Qual SampleRate Start End
- 7 fields: Net Sta Loc Cha SampleRate Start End
- 6 fields: Net Sta Cha SampleRate Start End
- 5 fields: Net Sta Cha Start End

Example:
#Network Station Location Channel Quality SampleRate Earliest Latest
HL       ACHA    --      HHZ     D       100.0      2011-01-18T00:00:00Z 2011-01-19T00:00:00Z

Requests are sent with User-Agent = "eida-consistency" to help node operators identify traffic.

Functions:
- check_availability_query() → check if a specific [start,end] is covered.
- get_availability_spans() → fetch all spans for a channel in one request.
"""

from __future__ import annotations
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

from eida_consistency.utils.constants import USER_AGENT


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _parse_text_availability(text: str) -> List[Dict[str, Any]]:
    """Parse text format availability response into spans with schema detection."""
    spans: List[Dict[str, Any]] = []
    lines = [ln for ln in text.strip().splitlines() if ln and not ln.startswith("#")]
    if not lines:
        return spans

    # Detect schema from first valid line
    schema_len = len(lines[0].split())
    logging.debug(f"[availability] Detected schema with {schema_len} fields")

    for line in lines:
        parts = line.split()
        if len(parts) != schema_len:
            logging.debug(f"[availability] Skipping inconsistent line: {line}")
            continue

        try:
            net, sta = parts[0], parts[1]
            start, end = parts[-2], parts[-1]

            # Validate timestamps
            _ = _parse_iso(start)
            _ = _parse_iso(end)

            loc, cha, qual, sr = "", None, None, None
            if schema_len == 8:
                # Net Sta Loc Cha Qual SR Start End
                loc, cha, qual, sr = parts[2], parts[3], parts[4], parts[5]
            elif schema_len == 7:
                # Net Sta Loc Cha SR Start End
                loc, cha, sr = parts[2], parts[3], parts[4]
            elif schema_len == 6:
                # Net Sta Cha SR Start End
                cha, sr = parts[2], parts[3]
            elif schema_len == 5:
                # Net Sta Cha Start End
                cha = parts[2]

            spans.append({
                "network": net,
                "station": sta,
                "location": "" if loc in ("--", "*") else loc,
                "channel": cha,
                "quality": qual,
                "samplerate": sr,
                "start": start,
                "end": end,
            })
        except Exception as e:
            logging.debug(f"[availability] Failed to parse line: {line} ({e})")
            continue

    return spans


def check_availability_query(
    base_url: str,
    network: str,
    station: str,
    channel: str,
    starttime: str,
    endtime: str,
    location: str = "*",
) -> Dict[str, Any]:
    """Query availability for a specific [start,end] and check coverage."""
    url = (
        f"{base_url}availability/1/query?"
        f"network={network}&station={station}&location={location}&channel={channel}"
        f"&start={starttime}&end={endtime}&format=text&merge=quality,overlap,gap"
    )
    logging.debug(f"Availability (query) URL: {url}")

    try:
        resp = requests.get(url, timeout=300, headers={"User-Agent": USER_AGENT})
        if resp.status_code == 204:
            return {"ok": False, "matched_span": None, "spans": [], "status": 204, "url": url}

        resp.raise_for_status()
        spans = _parse_text_availability(resp.text)
    except Exception as e:
        logging.error(f"Failed to parse availability TXT ({url}): {e}")
        return {"ok": False, "matched_span": None, "spans": [], "status": 0, "url": url}

    matched_span: Optional[Dict[str, Any]] = None
    ok = False

    try:
        e_start, e_end = _parse_iso(starttime), _parse_iso(endtime)
        for s in spans:
            try:
                s_start, s_end = _parse_iso(s["start"]), _parse_iso(s["end"])
            except Exception:
                continue
            if s_start <= e_start and s_end >= e_end:
                ok, matched_span = True, s
                break
    except Exception as e:
        logging.warning(f"Failed to check coverage: {e}")

    return {"ok": ok, "matched_span": matched_span, "spans": spans, "status": resp.status_code, "url": url}


def get_availability_spans(
    base_url: str,
    network: str,
    station: str,
    channel: str,
    starttime: str,
    endtime: str,
    location: str = "*",
) -> List[Dict[str, Any]]:
    """Fetch all spans for a channel in one request."""
    url = (
        f"{base_url}availability/1/query?"
        f"network={network}&station={station}&location={location}&channel={channel}"
        f"&start={starttime}&end={endtime}&format=text&merge=quality,overlap"
    )
    logging.debug(f"Availability (spans) URL: {url}")

    try:
        resp = requests.get(url, timeout=300, headers={"User-Agent": USER_AGENT})
        if resp.status_code == 204:
            return []

        resp.raise_for_status()
        spans = _parse_text_availability(resp.text)
        logging.debug(f"Fetched {len(spans)} spans for {network}.{station}.{channel}")
        return spans
    except Exception as e:
        logging.error(f"Failed to parse availability TXT ({url}): {e}")
        return []


def check_availability(
    base_url: str,
    network: str,
    station: str,
    channel: str,
    starttime: str,
    endtime: str,
    return_url: bool = False,
) -> str | Tuple[str, bool] | bool:
    result = check_availability_query(
        base_url, network, station, channel, starttime, endtime, location="*"
    )
    if return_url:
        return result["url"], bool(result["ok"])
    return bool(result["ok"])
