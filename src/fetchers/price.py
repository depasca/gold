"""Fetch current gold price and historical data via yfinance."""

from __future__ import annotations

import logging
from typing import TypedDict

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)


class OHLCVBar(TypedDict):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class PriceSnapshot(TypedDict):
    current: float
    prev_close: float
    change_24h: float
    change_pct_24h: float
    change_7d_pct: float
    change_30d_pct: float
    high_52w: float
    low_52w: float
    history_30d: list[OHLCVBar]
    closes_1y: list[float]  # full year of closes for signal computation


def fetch_price() -> PriceSnapshot:
    """Fetch COMEX gold futures (GC=F) price and 1-year history."""
    ticker = yf.Ticker("GC=F")
    hist: pd.DataFrame = ticker.history(period="1y")

    if hist.empty:
        raise RuntimeError("Failed to fetch gold price data from Yahoo Finance")

    closes = hist["Close"]
    n = len(closes)

    current = float(closes.iloc[-1])
    prev_close = float(closes.iloc[-2]) if n >= 2 else current
    close_7d_ago = float(closes.iloc[max(0, n - 8)])
    close_30d_ago = float(closes.iloc[max(0, n - 31)])

    history_30d: list[OHLCVBar] = []
    for ts, row in hist.tail(30).iterrows():
        history_30d.append(
            {
                "date": str(pd.Timestamp(ts).date()),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": float(row["Volume"]),
            }
        )

    return {
        "current": round(current, 2),
        "prev_close": round(prev_close, 2),
        "change_24h": round(current - prev_close, 2),
        "change_pct_24h": round((current - prev_close) / prev_close * 100, 3),
        "change_7d_pct": round((current - close_7d_ago) / close_7d_ago * 100, 3),
        "change_30d_pct": round((current - close_30d_ago) / close_30d_ago * 100, 3),
        "high_52w": round(float(hist["High"].max()), 2),
        "low_52w": round(float(hist["Low"].min()), 2),
        "history_30d": history_30d,
        "closes_1y": [round(float(c), 2) for c in closes.tolist()],
    }
