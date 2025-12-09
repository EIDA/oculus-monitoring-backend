"""Node utilities for managing EIDA node information."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from appdirs import user_cache_dir

ROUTING_URL = (
    "https://www.orfeus-eu.org/eidaws/routing/1/globalconfig?format=fdsn"
)
CACHE_FILE = Path(user_cache_dir("eida_consistency")) / "nodes_cache.json"

DEFAULT_NODES = [
    ("GFZ", "https://geofon.gfz.de/fdsnws/", True),
    ("ODC", "https://orfeus-eu.org/fdsnws/", True),
    ("ETHZ", "https://eida.ethz.ch/fdsnws/", True),
    ("RESIF", "https://ws.resif.fr/fdsnws/", True),
    ("INGV", "https://webservices.ingv.it/fdsnws/", True),
    ("LMU", "https://erde.geophysik.uni-muenchen.de/fdsnws/", True),
    ("ICGC", "https://ws.icgc.cat/fdsnws/", True),
    ("NOA", "https://eida.gein.noa.gr/fdsnws/", True),
    ("BGR", "https://eida.bgr.de/fdsnws/", True),
    ("BGS", "https://eida.bgs.ac.uk/fdsnws/", True),
    ("NIEP", "https://eida-sc3.infp.ro/fdsnws/", True),
    ("KOERI", "https://eida.koeri.boun.edu.tr/fdsnws/", True),
    ("UIB-NORSAR", "https://eida.geo.uib.no/fdsnws/", True),
]


def ensure_cache_dir() -> None:
    """Ensure the cache directory exists."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


def refresh_cache_from_routing() -> list[tuple[str, str, bool]]:
    """Fetch node list from routing service and cache it."""
    import logging
    import requests

    try:
        response = requests.get(ROUTING_URL, timeout=30)
        response.raise_for_status()
    except Exception as exc:
        raise RuntimeError("Failed to fetch routing data") from exc

    nodes: list[tuple[str, str, bool]] = []
    for dc in response.json().get("datacenters", []):
        name = dc.get("name")
        for repo in dc.get("repositories", []):
            for srv in repo.get("services", []):
                if srv.get("name") == "fdsnws-station-1":
                    url = srv["url"]
                    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}/fdsnws/"
                    nodes.append((name, base, True))
                    break
            if name and nodes and nodes[-1][0] == name:
                break

    CACHE_FILE.write_text(json.dumps({"nodes": nodes}), encoding="utf-8")
    return nodes


def load_or_refresh_cache() -> list[tuple[str, str, bool]]:
    """Return cached nodes or refresh from routing."""
    ensure_cache_dir()
    if CACHE_FILE.exists():
        try:
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            nodes = data.get("nodes", [])
            if all(isinstance(n, list) and len(n) == 3 for n in nodes):
                return [(n[0], n[1], n[2]) for n in nodes]
        except Exception:  # noqa: BLE001
            CACHE_FILE.unlink()

    try:
        return refresh_cache_from_routing()
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.warning("Routing failed: %s", exc)
        return DEFAULT_NODES


def load_node_url(node_name: str) -> str:
    """Return the FDSN base URL for a given node short name."""
    for name, url, _ in load_or_refresh_cache():
        if name.upper() == node_name.upper():
            return url
    raise ValueError(f"Unknown node: {node_name}")


def get_obspy_url(base_url: str) -> str:
    """Convert an FDSN base URL to plain HTTP host name for ObsPy.

    Example:
    -------
    get_obspy_url("https://eida.gein.noa.gr/fdsnws/")
    'http://eida.gein.noa.gr'

    """
    hostname = urlparse(base_url).hostname
    return f"http://{hostname}" if hostname else base_url