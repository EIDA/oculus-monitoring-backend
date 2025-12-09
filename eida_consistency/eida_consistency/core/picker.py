"""Random candidate picker for consistency checks.

Utility to select a waveform request candidate whose time window
is longer than two minutes.
"""
import logging
import random
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

def pick_random_candidate(candidates: list) -> dict | None:
    """Pick a random candidate whose time window exceeds 2 minutes.

    The list is shuffled in-place. The first candidate with a
    duration ≥ 120 s is returned.  Malformed or short candidates are
    skipped and logged at DEBUG level.

    Parameters
    ----------
    candidates : list[dict]
        Each dict must contain at least the key ``"starttime"``
        (ISO-8601 string).  If ``"endtime"`` is omitted, the window
        is assumed to be 10 minutes long.

    Returns
    -------
    dict | None
        A shallow copy of the chosen candidate with ``starttime`` and
        ``endtime`` replaced by normalized ISO-8601 strings, or
        ``None`` when no suitable candidate is found.

    """
    logging.getLogger(__name__).info("Picking random candidate...")
    random.shuffle(candidates)

    for candidate in candidates:
        try:
            logging.debug(f"Evaluating candidate: {candidate}")
            start = datetime.fromisoformat(candidate["starttime"].replace("Z", ""))
            end_str = candidate.get("endtime")
            end = datetime.fromisoformat(end_str.replace("Z", "")) if end_str else start + timedelta(minutes=10)
            duration = (end - start).total_seconds()

            logging.debug(f"Duration: {duration} seconds")

            if duration < 120:
                logging.debug("Duration too short, skipping.")
                continue

            logging.info("✅ Valid candidate found.")
            return {
                **candidate,
                "starttime": start.isoformat(),
                "endtime": end.isoformat()
            }
        except Exception as e:
            logging.debug(f"Skipping candidate due to error: {e}")
            continue

    logging.warning("No valid candidate found.")
    return None
