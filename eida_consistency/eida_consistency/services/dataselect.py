"""EIDA **dataselect** web-service.

Robust waveform fetch:
- Use ObsPy FDSN Client first (HTTPS, exact location, timeout).
- On AttributeError / client hiccups, fall back to raw HTTP GET and parse with obspy.read().
"""

from __future__ import annotations

import traceback
from io import BytesIO
from urllib.parse import urlparse
from eida_consistency.utils.constants import USER_AGENT
import requests
from obspy.clients.fdsn import Client
from obspy import UTCDateTime, read


def _endpoint_from_base(base_url: str) -> str:
    """Preserve scheme/host (e.g. https://ws.resif.fr)."""
    p = urlparse(base_url)
    scheme = p.scheme or "https"
    host = p.hostname or ""
    return f"{scheme}://{host}".rstrip("/")


def _build_query_url(endpoint: str, net: str, sta: str, loc: str, cha: str, start: str, end: str) -> str:
    return (
        f"{endpoint}/fdsnws/dataselect/1/query?"
        f"network={net}&station={sta}&location={loc}&channel={cha}"
        f"&starttime={start}&endtime={end}&nodata=204"
    )


def dataselect(
    base_url: str,
    net: str,
    sta: str,
    cha: str,
    start: str,
    end: str,
    loc: str = "",
    return_stream: bool = False,
    timeout: int = 20,
):
    """
    Returns:
        dict: {
          success, status, type, error, debug, [stream]
        }
    """
    endpoint = _endpoint_from_base(base_url)
    loc_code = (loc or "").strip()  # exact location only, no wildcard

    # Attempt #1 — ObsPy FDSN Client
    q1 = _build_query_url(endpoint, net, sta, loc_code, cha, start, end)
    try:
        client = Client(endpoint, timeout=timeout, user_agent=USER_AGENT)
        st = client.get_waveforms(
            network=net, station=sta, location=loc_code, channel=cha,
            starttime=UTCDateTime(start), endtime=UTCDateTime(end)
        )
        n = len(st)
        if n == 0:
            return {
                "success": False, "status": "NoData", "type": "NoTrace", "error": None,
                "debug": f"❌ No waveform data (ObsPy client).\n{q1}",
            }
        info = "\n".join(str(tr) for tr in st)
        res = {
            "success": True, "status": "OK",
            "type": "MultiTrace" if n > 1 else "SingleTrace",
            "error": None, "debug": f"✅ Retrieved {n} trace(s) via ObsPy client.\n{info}\n{q1}",
        }
        if return_stream:
            res["stream"] = st
        return res

    except AttributeError as e_attr:
        # Known oddity: sometimes ObsPy hits AttributeError in internal path.
        # Fall back to raw HTTP + obspy.read
        pass
    except Exception as e:
        # Other failures also fall back
        pass

    # Attempt #2 — raw HTTP GET + obspy.read
    try:
        r = requests.get(q1, timeout=timeout, headers={"User-Agent": USER_AGENT})
        if r.status_code == 204 or not r.content:
            return {
                "success": False, "status": "NoData", "type": "NoTrace", "error": None,
                "debug": f"❌ No waveform bytes (HTTP {r.status_code}).\n{q1}",
            }

        # Try to parse MiniSEED from the raw bytes
        bio = BytesIO(r.content)
        st = read(bio, format="MSEED")
        n = len(st)
        if n == 0:
            return {
                "success": False, "status": "ParseError", "type": "NoTrace", "error": None,
                "debug": f"❌ Could not parse MiniSEED from HTTP bytes.\n{q1}",
            }

        info = "\n".join(str(tr) for tr in st)
        res = {
            "success": True, "status": "OK",
            "type": "MultiTrace" if n > 1 else "SingleTrace",
            "error": None, "debug": f"✅ Retrieved {n} trace(s) via raw HTTP+read().\n{info}\n{q1}",
        }
        if return_stream:
            res["stream"] = st
        return res

    except Exception as e2:
        return {
            "success": False, "status": type(e2).__name__, "type": "Error",
            "error": traceback.format_exc(),
            "debug": f"❌ Dataselect failed (both client and raw).\n{q1}",
        }
