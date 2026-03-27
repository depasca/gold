"""Compute technical indicators from 1-year gold price history."""

from __future__ import annotations

import logging
from typing import TypedDict

import numpy as np
import pandas as pd

from src.fetchers.price import PriceSnapshot

log = logging.getLogger(__name__)


class TechnicalSignals(TypedDict):
    rsi_14: float
    ma_20: float
    ma_50: float
    ma_200: float
    price_vs_ma20_pct: float
    price_vs_ma50_pct: float
    price_vs_ma200_pct: float
    ma20_trend: str      # up | down | flat
    rsi_signal: str      # overbought | oversold | neutral
    momentum_signal: str  # strong_up | up | flat | down | strong_down


def _rsi(series: pd.Series, period: int = 14) -> float:
    if len(series) < period + 1:
        return 50.0
    delta = series.diff().dropna()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    val = rsi.iloc[-1]
    return round(float(val) if not np.isnan(val) else 50.0, 1)


def _sma(series: pd.Series, window: int) -> float:
    if len(series) < window:
        return round(float(series.mean()), 2)
    return round(float(series.tail(window).mean()), 2)


def compute_signals(price: PriceSnapshot) -> TechnicalSignals:
    """Compute RSI(14), MA20/50/200, and momentum from 1-year close history."""
    closes = pd.Series(price["closes_1y"], dtype=float)
    current = price["current"]

    rsi = _rsi(closes)
    ma20 = _sma(closes, 20)
    ma50 = _sma(closes, 50)
    ma200 = _sma(closes, 200)

    # Short-term trend: compare last 5 bars vs previous 5 bars
    if len(closes) >= 10:
        recent = float(closes.iloc[-5:].mean())
        prior = float(closes.iloc[-10:-5].mean())
        if recent > prior * 1.003:
            ma20_trend = "up"
        elif recent < prior * 0.997:
            ma20_trend = "down"
        else:
            ma20_trend = "flat"
    else:
        ma20_trend = "flat"

    rsi_signal = (
        "overbought" if rsi > 70
        else "oversold" if rsi < 30
        else "neutral"
    )

    m7d = price["change_7d_pct"]
    momentum_signal = (
        "strong_up" if m7d > 3
        else "up" if m7d > 1
        else "flat" if abs(m7d) <= 1
        else "down" if m7d > -3
        else "strong_down"
    )

    return {
        "rsi_14": rsi,
        "ma_20": ma20,
        "ma_50": ma50,
        "ma_200": ma200,
        "price_vs_ma20_pct": round((current - ma20) / ma20 * 100, 2),
        "price_vs_ma50_pct": round((current - ma50) / ma50 * 100, 2),
        "price_vs_ma200_pct": round((current - ma200) / ma200 * 100, 2),
        "ma20_trend": ma20_trend,
        "rsi_signal": rsi_signal,
        "momentum_signal": momentum_signal,
    }
