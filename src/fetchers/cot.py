"""Fetch CFTC Commitments of Traders data for COMEX gold futures.

Uses the CFTC public Socrata API — no API key required.
Legacy COT report: https://publicreporting.cftc.gov/resource/6dca-aqww.json
"""

from __future__ import annotations

import logging
from typing import TypedDict

import requests

log = logging.getLogger(__name__)

CFTC_ENDPOINT = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
GOLD_MARKET = "GOLD - COMMODITY EXCHANGE INC."


class COTSnapshot(TypedDict):
    report_date: str
    open_interest: int
    noncomm_long: int
    noncomm_short: int
    noncomm_net: int       # speculative net (non-commercial long − short)
    comm_long: int
    comm_short: int
    comm_net: int          # commercial (hedger) net
    net_change_week: int   # week-over-week change in noncomm_net
    weeks_available: int


def _to_int(row: dict, key: str) -> int:
    try:
        return int(float(str(row.get(key) or 0)))
    except (ValueError, TypeError):
        return 0


def fetch_cot() -> COTSnapshot:
    """Fetch last two weekly COT reports for COMEX gold from CFTC."""
    # Build URL with literal $-prefixed Socrata params — requests.get(params=...)
    # percent-encodes $ → %24, which Socrata rejects with a 400.
    from urllib.parse import quote
    market_enc = quote(GOLD_MARKET, safe="")
    url = (
        f"{CFTC_ENDPOINT}"
        f"?market_and_exchange_names={market_enc}"
        f"&$order=report_date_as_yyyy_mm_dd+DESC"
        f"&$limit=2"
    )
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    rows: list[dict] = resp.json()

    if not rows:
        raise RuntimeError("CFTC API returned no COT data for gold")

    latest = rows[0]
    noncomm_long = _to_int(latest, "noncomm_positions_long_all")
    noncomm_short = _to_int(latest, "noncomm_positions_short_all")
    noncomm_net = noncomm_long - noncomm_short

    comm_long = _to_int(latest, "comm_positions_long_all")
    comm_short = _to_int(latest, "comm_positions_short_all")
    comm_net = comm_long - comm_short

    net_change = 0
    if len(rows) >= 2:
        prev = rows[1]
        prev_net = _to_int(prev, "noncomm_positions_long_all") - _to_int(prev, "noncomm_positions_short_all")
        net_change = noncomm_net - prev_net

    return {
        "report_date": latest.get("report_date_as_yyyy_mm_dd", "unknown"),
        "open_interest": _to_int(latest, "open_interest_all"),
        "noncomm_long": noncomm_long,
        "noncomm_short": noncomm_short,
        "noncomm_net": noncomm_net,
        "comm_long": comm_long,
        "comm_short": comm_short,
        "comm_net": comm_net,
        "net_change_week": net_change,
        "weeks_available": len(rows),
    }
