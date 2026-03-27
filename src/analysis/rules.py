"""Rule-based gold market scoring — deterministic, no API calls required."""

from __future__ import annotations

import logging

from src.analysis.signals import TechnicalSignals
from src.analysis.types import GoldRecommendation
from src.fetchers.cot import COTSnapshot
from src.fetchers.news import NewsItem
from src.fetchers.price import PriceSnapshot

log = logging.getLogger(__name__)

_BULLISH_KEYWORDS: frozenset[str] = frozenset(
    {"rally", "surge", "gain", "safe haven", "buying", "record", "high", "rise", "inflow"}
)
_BEARISH_KEYWORDS: frozenset[str] = frozenset(
    {"drop", "fall", "sell-off", "rate hike", "strong dollar", "outflow", "decline", "slump"}
)

_MOMENTUM_SCORES: dict[str, int] = {
    "strong_up": 20,
    "up": 10,
    "flat": 0,
    "down": -10,
    "strong_down": -20,
}

_TREND_SCORES: dict[str, int] = {"up": 8, "flat": 0, "down": -8}


def _technical_score(signals: TechnicalSignals) -> int:
    score = 0

    # RSI signal: ±15
    if signals["rsi_signal"] == "oversold":
        score += 15
    elif signals["rsi_signal"] == "overbought":
        score -= 15

    # Price vs MA50: ±10
    score += 10 if signals["price_vs_ma50_pct"] > 0 else -10

    # Price vs MA200: ±5
    score += 5 if signals["price_vs_ma200_pct"] > 0 else -5

    # Momentum: strong_up +20 → strong_down -20
    score += _MOMENTUM_SCORES.get(signals["momentum_signal"], 0)

    # MA20 trend: ±8
    score += _TREND_SCORES.get(signals["ma20_trend"], 0)

    return score


def _cot_score(cot: COTSnapshot) -> int:
    nc = cot["net_change_week"]
    if nc > 2000:
        return 10
    if nc > 0:
        return 5
    if nc < -2000:
        return -10
    return -5


def _news_score(news: list[NewsItem]) -> int:
    bullish = sum(
        1 for item in news for kw in _BULLISH_KEYWORDS if kw in item["title"].lower()
    )
    bearish = sum(
        1 for item in news for kw in _BEARISH_KEYWORDS if kw in item["title"].lower()
    )
    return max(-15, min(15, (bullish - bearish) * 3))


def score(
    price: PriceSnapshot,
    signals: TechnicalSignals,
    news: list[NewsItem],
    cot: COTSnapshot,
) -> GoldRecommendation:
    """Produce a GoldRecommendation via deterministic rule scoring. No API calls."""
    tech = _technical_score(signals)
    cot_pts = _cot_score(cot)
    news_pts = _news_score(news)
    total = tech + cot_pts + news_pts

    log.info(
        "Rule scores — technical: %+d  COT: %+d  news: %+d  total: %+d",
        tech, cot_pts, news_pts, total,
    )

    if total >= 20:
        outlook, recommendation = "bullish", "buy"
        low_mult, high_mult = 1.005, 1.015
    elif total <= -20:
        outlook, recommendation = "bearish", "sell"
        low_mult, high_mult = 0.985, 0.995
    else:
        outlook, recommendation = "neutral", "hold"
        low_mult, high_mult = 0.995, 1.005

    confidence = min(90, 50 + abs(total) // 2)
    current = price["current"]

    summary = (
        f"Rule-based analysis scores {total:+d} points overall. "
        f"Technical indicators show {signals['momentum_signal'].replace('_', ' ')} momentum "
        f"with RSI at {signals['rsi_14']} ({signals['rsi_signal']}). "
        f"Speculative positioning shifted {cot['net_change_week']:+,} contracts week-over-week."
    )

    return {
        "price_outlook": outlook,
        "confidence": confidence,
        "recommendation": recommendation,
        "forecast_7d_low": round(current * low_mult, 2),
        "forecast_7d_high": round(current * high_mult, 2),
        "key_factors": [
            f"Momentum: {signals['momentum_signal'].replace('_', ' ')} "
            f"(7d change: {price['change_7d_pct']:+.2f}%)",
            f"Price vs MA50: {signals['price_vs_ma50_pct']:+.2f}%  |  "
            f"vs MA200: {signals['price_vs_ma200_pct']:+.2f}%",
            f"COT speculative net WoW change: {cot['net_change_week']:+,} contracts",
        ],
        "risks": [
            "Rule-based model does not account for breaking macro events or news nuance",
            "Keyword sentiment scoring may miss context; consider --mode=api for deeper analysis",
        ],
        "summary": summary,
    }
