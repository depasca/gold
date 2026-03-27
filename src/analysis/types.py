"""Shared type definitions for gold analysis outputs."""

from __future__ import annotations

from typing import TypedDict


class GoldRecommendation(TypedDict):
    price_outlook: str        # bullish | neutral | bearish
    confidence: int           # 0–100
    recommendation: str       # buy | hold | sell
    forecast_7d_low: float
    forecast_7d_high: float
    key_factors: list[str]
    risks: list[str]
    summary: str
