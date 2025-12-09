"""Day-level availability checks for EIDA.

For a given day, fetch availability spans (TXT) and test consistency
against a random 10-minute dataselect window inside that day.
"""

from __future__ import annotations
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List

import requests

from eida_consistency.services.dataselect import dataselect
from eida_consistency.utils.constants import USER_AGENT


def _normalize_location(loc: str | None) -> str:
    """Ensure location is valid for FDSN queries."""
    if not loc or not str(loc).strip():
        return "*"
    return loc


def _parse_iso(s: str) -> datetime:
    """Parse ISO string into UTC-aware datetime."""
    dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_text_availability(text: str) -> List[Dict[str, Any]]:
    """Parse text format availability response into spans."""
    spans: List[Dict[str, Any]] = []
    lines = text.strip().splitlines()
    for line in lines:
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        # 7 fields → no SampleRate, 8 fields → includes SampleRate
        if len(parts) == 7:
            net, sta, loc, cha, qual, start, end = parts
            spans.append({
                "network": net,
                "station": sta,
                "location": "" if loc in ("--", "*") else loc,
                "channel": cha,
                "quality": qual,
                "start": start,
                "end": end,
            })
        elif len(parts) >= 8:
            net, sta, loc, cha, qual, samplerate, start, end = parts[:8]
            spans.append({
                "network": net,
                "station": sta,
                "location": "" if loc in ("--", "*") else loc,
                "channel": cha,
                "quality": qual,
                "samplerate": samplerate,
                "start": start,
                "end": end,
            })
    return spans


def check_day_availability(
    base_url: str,
    network: str,
    station: str,
    channel: str,
    day: datetime,
    location: str | None = "*",
    verbose: bool = False,
) -> Dict[str, Any]:
    """Check if availability covers a random 10-min dataselect window in a given day."""

    # Normalize location
    location = _normalize_location(location)

    # Day boundaries
    t0 = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    t1 = datetime.combine(day, datetime.max.time(), tzinfo=timezone.utc)

    # Build availability URL (TXT + merged spans)
    avail_url = (
        f"{base_url}availability/1/query?"
        f"network={network}&station={station}&location={location}&channel={channel}"
        f"&start={t0.isoformat()}&end={t1.isoformat()}&format=text&merge=quality,overlap"
    )
    if verbose:
        logging.info(f"  Availability URL: {avail_url}")

    # Fetch availability spans
    try:
        resp = requests.get(avail_url, timeout=20, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        spans = _parse_text_availability(resp.text)
    except Exception as e:
        logging.error(f"[DayAvailability] Request failed: {e}")
        return {"ok": False, "consistent": False, "availability_url": avail_url, "dataselect_url": None}

    if not spans:
        return {"ok": False, "consistent": False, "availability_url": avail_url, "dataselect_url": None}

    # Pick random 10-min window
    rand_offset = random.randint(0, int((t1 - t0).total_seconds()) - 600)
    ds_start = t0 + timedelta(seconds=rand_offset)
    ds_end = ds_start + timedelta(minutes=10)

    # Check if availability spans cover this window
    covered = any(
        _parse_iso(s["start"]) <= ds_start and _parse_iso(s["end"]) >= ds_end
        for s in spans
    )

    # Run dataselect for the 10-min window
    ds_result = dataselect(
        base_url, network, station, channel,
        ds_start.isoformat(), ds_end.isoformat(), location
    )
    ds_url = ds_result.get("url")

    if verbose and ds_url:
        logging.info(f"  Dataselect URL:   {ds_url}")
        logging.info(
            f"  Result → availability covered={covered}, "
            f"dataselect success={ds_result['success']}, "
            f"consistent={covered == ds_result['success']}"
        )

    return {
        "ok": True,
        "consistent": covered == ds_result["success"],
        "availability_url": avail_url,
        "dataselect_url": ds_url,
        "availability_covered": covered,
        "dataselect_success": ds_result["success"],
    }
