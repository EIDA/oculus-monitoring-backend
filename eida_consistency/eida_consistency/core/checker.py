"""Pick random epochs and check availability coverage (returns location and matched span).

This module selects up to `epochs` unique (network, station, channel) items from the
candidate pool. For each channel, it queries /availability/1/query?format=json once for
the entire epoch-span (from StationXML). Then, within that span, it picks random test
epochs of length `duration` seconds.

Return value:
    results, stats

results = [
      (
        availability_url,    # the availability request URL (full epoch-span)
        availability_ok,     # True/False depending on slice coverage
        epoch_start_iso,     # slice start
        epoch_end_iso,       # slice end
        location_exact,      # location code (from matched span or StationXML)
        matched_span         # the span dict that covered the slice (or None)
      ),
      ...
]

stats = {
    "candidates_requested": epochs,
    "candidates_generated": len(results),
    "candidates_pool": len(pool),
    "queries_performed": attempts,
}
"""

from __future__ import annotations

import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from eida_consistency.services.availability import get_availability_spans


def _parse_iso(dt: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 string (tolerate trailing 'Z')."""
    if not dt or not str(dt).strip():
        return None
    try:
        return datetime.fromisoformat(str(dt).replace("Z", ""))
    except Exception:
        return None


def _inside_any_span(
    t0: datetime, t1: datetime, spans: List[Dict[str, str]]
) -> Tuple[bool, Dict[str, str] | None]:
    """Check if [t0, t1] is fully covered by any availability span."""
    for s in spans:
        try:
            s_start, s_end = _parse_iso(s["start"]), _parse_iso(s["end"])
        except Exception:
            continue
        if not s_start or not s_end:
            continue
        if s_start <= t0 and s_end >= t1:
            return True, s
    return False, None


def check_candidate(
    base_url: str,
    candidate: Dict[str, str],
    candidates: Optional[List[Dict[str, str]]] = None,
    epochs: int = 10,
    duration: int = 600,
) -> Tuple[List[Tuple[str, bool, str, str, str, Dict[str, str] | None]], Dict[str, int]]:
    """
    Build up to `epochs` test cases and check availability coverage.

    Returns
    -------
    results : list of tuples
        (availability_url, availability_ok, epoch_start_iso, epoch_end_iso,
         location_exact, matched_span)
    stats : dict
        {"candidates_requested", "candidates_generated", "candidates_pool", "queries_performed"}
    """
    if duration < 600:
        raise ValueError("Duration must be at least 600 seconds (10 minutes).")

    results: List[Tuple[str, bool, str, str, str, Dict[str, str] | None]] = []

    pool = [
        c for c in (candidates or [candidate])
        if all(k in c for k in ("network", "station", "channel", "starttime"))
    ]
    if not pool:
        return results, {
            "candidates_requested": epochs,
            "candidates_generated": 0,
            "candidates_pool": 0,
            "queries_performed": 0,
        }

    used: set[tuple[str, str, str]] = set()
    attempts, max_attempts = 0, max(epochs * 20, len(pool) * 2)

    while len(results) < epochs and attempts < max_attempts:
        attempts += 1
        sample = random.choice(pool)
        key = (sample["network"], sample["station"], sample["channel"])
        if key in used:
            continue

        ch_start = _parse_iso(sample.get("starttime"))
        ch_end = _parse_iso(sample.get("endtime")) or datetime.utcnow()
        if not ch_start or not ch_end or ch_start >= ch_end:
            continue

        # Fetch availability spans once for this channel epoch-span
        spans = get_availability_spans(
            base_url,
            sample["network"],
            sample["station"],
            sample["channel"],
            sample["starttime"],
            sample.get("endtime") or datetime.utcnow().isoformat(),
            location=sample.get("location", "*"),
        )
        if not spans:
            continue

        # Random slice of `duration` seconds inside [ch_start, ch_end]
        duration_td = timedelta(seconds=duration)
        latest_start = ch_end - duration_td
        if ch_start >= latest_start:
            continue

        offset = random.randint(0, int((latest_start - ch_start).total_seconds()))
        epoch_start_dt = ch_start + timedelta(seconds=offset)
        epoch_end_dt = epoch_start_dt + duration_td

        s = epoch_start_dt.strftime("%Y-%m-%dT%H:%M:%S")
        e = epoch_end_dt.strftime("%Y-%m-%dT%H:%M:%S")

        available, matched_span = _inside_any_span(epoch_start_dt, epoch_end_dt, spans)
        loc = matched_span["location"] if (matched_span and matched_span.get("location")) else sample.get("location", "")

        # Availability request URL (for reproducibility/debugging)
        url = (
            f"{base_url}availability/1/query?"
            f"network={sample['network']}&station={sample['station']}"
            f"&location={sample.get('location','*')}&channel={sample['channel']}"
            f"&start={sample['starttime']}&end={sample.get('endtime') or datetime.utcnow().isoformat()}"
            f"&format=text"
        )

        logging.debug(f"Availability request URL used: {url}")

        results.append((url, available, s, e, loc, matched_span))
        used.add(key)

    # Final summary line
    logging.info(
        f"Final usable epochs: {len(results)} / {epochs} "
        f"(from {len(pool)} channel candidates, {attempts} attempts)"
    )

    stats = {
        "candidates_requested": epochs,
        "candidates_generated": len(results),
        "candidates_pool": len(pool),
        "queries_performed": attempts,
    }

    return results, stats
