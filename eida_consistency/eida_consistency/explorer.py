"""Explore inconsistency boundaries around reported results."""

import json
import logging
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from eida_consistency.services.availability import get_availability_spans
from eida_consistency.services.dataselect import dataselect
from eida_consistency.utils.nodes import load_node_url


def _parse_iso(s: str) -> datetime:
    """Parse ISO string into UTC-aware datetime."""
    if not s:
        return None
    dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    """Format datetime as UTC ISO string (second precision)."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _slice_consistent(
    base_url: str,
    net: str,
    sta: str,
    cha: str,
    loc: str,
    t0: datetime,
    t1: datetime,
    verbose: bool = False,
) -> bool:
    """
    Check if a time slice is consistent between availability and dataselect.
    Returns True if consistent, False if inconsistent.
    """
    # 1. Get availability spans for this slice
    spans = get_availability_spans(
        base_url, net, sta, cha, _iso(t0), _iso(t1), location=loc or "*"
    )
    covered = any(
        _parse_iso(s["start"]) <= t0 and _parse_iso(s["end"]) >= t1
        for s in spans
    )

    # 2. Pick random 10-min window
    day_seconds = int((t1 - t0).total_seconds())
    if day_seconds > 600:
        offset = random.randint(0, day_seconds - 600)
        ds_t0 = t0 + timedelta(seconds=offset)
        ds_t1 = ds_t0 + timedelta(seconds=600)
    else:
        ds_t0, ds_t1 = t0, t1

    # 3. Run dataselect
    ds = dataselect(base_url, net, sta, cha, _iso(ds_t0), _iso(ds_t1), loc)

    consistent = covered == ds["success"]

    # 4. Logging
    if verbose:
        logging.info(
            f"  Availability URL: {base_url}availability/1/query?"
            f"network={net}&station={sta}&location={loc}&channel={cha}"
            f"&start={_iso(t0)}&end={_iso(t1)}&format=json"
        )
        logging.info(
            f"  Dataselect URL:   {base_url}dataselect/1/query?"
            f"network={net}&station={sta}&location={loc}&channel={cha}"
            f"&starttime={_iso(ds_t0)}&endtime={_iso(ds_t1)}&nodata=204"
        )
        logging.info(
            f"  Result → availability covered={covered}, "
            f"dataselect success={ds['success']}, "
            f"consistent={consistent}"
        )
    else:
        logging.info(f"  Checked {t0.date()} → consistent={consistent}")

    return consistent


def explore_boundaries(
    report_path: str | Path,
    indices: Optional[List[int]] = None,
    max_days: int = 30,
    verbose: bool = False,
) -> None:
    """
    Explore inconsistencies from a report.
    If indices is None, explores all inconsistent entries.
    """
    report = json.loads(Path(report_path).read_text())
    results = report["results"]

    # Filter results
    if indices:
        targets = [r for r in results if r["index"] in indices]
    else:
        targets = [r for r in results if not r["consistent"]]

    if not targets:
        logging.info("No targets to explore (all consistent or no matching index).")
        return

    node = report["summary"]["node"]
    base_url = load_node_url(node)

    for r in targets:
        if r.get("consistent", False):
            logging.info(
                f"Index {r['index']} is marked consistent in the report → skipping."
            )
            continue

        net, sta, cha, loc = r["network"], r["station"], r["channel"], r["location"]
        slice_start = _parse_iso(r["starttime"])
        slice_end = _parse_iso(r["endtime"])

        logging.info(
            f"Exploring inconsistency for {net}.{sta}.{loc}.{cha} "
            f"(index={r['index']}) around {slice_start} → {slice_end}"
        )

        # --- Walk backward ---
        back = slice_start.date()
        checked = 0
        while checked < max_days:
            prev_day = back - timedelta(days=1)
            t0 = datetime.combine(prev_day, datetime.min.time(), tzinfo=timezone.utc)
            t1 = datetime.combine(prev_day, datetime.max.time(), tzinfo=timezone.utc)

            if _slice_consistent(base_url, net, sta, cha, loc, t0, t1, verbose):
                logging.info("  Day was consistent, stopping backward search.")
                break
            back = prev_day
            checked += 1
        else:
            logging.warning(f"Reached max backward search limit ({max_days} days).")

        # --- Walk forward ---
        forward = slice_end.date()
        checked = 0
        while checked < max_days:
            next_day = forward + timedelta(days=1)
            t0 = datetime.combine(next_day, datetime.min.time(), tzinfo=timezone.utc)
            t1 = datetime.combine(next_day, datetime.max.time(), tzinfo=timezone.utc)

            if _slice_consistent(base_url, net, sta, cha, loc, t0, t1, verbose):
                logging.info("  Day was consistent, stopping forward search.")
                break
            forward = next_day
            checked += 1
        else:
            logging.warning(f"Reached max forward search limit ({max_days} days).")

        # Report the expanded window
        logging.info(f"Inconsistency window: {back} → {forward}")

        # Suggested action
        if r["available"] and not r["dataselect_success"]:
            cmd = "clean"
            explanation = "Availability shows data but dataselect failed, cleaning is needed."
        elif not r["available"] and r["dataselect_success"]:
            cmd = "refresh"
            explanation = "Dataselect has data but availability disagrees, refreshing is needed."
        else:
            cmd = "refresh"
            explanation = "Inconsistency detected, unclear direction. Defaulting to 'refresh'."

        logging.info(f"Suggested action: {explanation}")
        logging.info(
            "Command:\n"
            f"uvx dmtri {cmd} --network={net} --station={sta} --channel={cha} "
            f"--start={back} --end={forward}"
        )
