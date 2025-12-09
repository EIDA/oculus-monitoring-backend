"""Run consistency tests against all cached EIDA nodes.

Each node will get its own subfolder in reports/nodes/<node>/.
"""

import logging
from pathlib import Path

from eida_consistency.utils import nodes
from eida_consistency.runner import run_consistency_check
from eida_consistency.report.report import REPORT_DIR
from eida_consistency.services.station import fetch_candidates

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


def main():
    # Load all nodes (cached or from routing)
    all_nodes = nodes.load_or_refresh_cache()
    logging.info(f"Testing {len(all_nodes)} nodes...")

    for name, url, enabled in all_nodes:
        # Skip closed or problematic nodes
        if name.upper() in {"ICGC", "INGV"}:
            logging.info(f"Skipping {name} node (closed or unstable).")
            continue

        if not enabled:
            logging.info(f"Skipping disabled node {name}")
            continue

        node_dir = REPORT_DIR / "nodes" / name.lower()
        node_dir.mkdir(parents=True, exist_ok=True)

        logging.info(f"--- Running test for node: {name} ({url}) ---")

        try:
            # First, probe how many candidates we can actually fetch
            requested = 100
            candidates = fetch_candidates(url, max_stations=requested)
            found = len(candidates)

            

            if found == 0:
                logging.warning(f"Skipping {name}: no candidates found.")
                continue

            # Now run the consistency check using available candidates
            run_consistency_check(
                node=name,
                epochs=20,        # 20 epochs per node
                duration=600,     # 10 minutes per epoch
                seed=None,        # random seed
                report_dir=node_dir,
            )

        except Exception as exc:
            logging.error(f"Node {name} failed with error: {exc}")


if __name__ == "__main__":
    main()
