"""Claude-powered gold market analysis — uses claude-opus-4-6 with adaptive thinking."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import TypedDict

import anthropic

from src.analysis.signals import TechnicalSignals
from src.fetchers.cot import COTSnapshot
from src.fetchers.news import NewsItem
from src.fetchers.price import PriceSnapshot

log = logging.getLogger(__name__)

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")


class GoldRecommendation(TypedDict):
    price_outlook: str       # bullish | neutral | bearish
    confidence: int          # 0–100
    recommendation: str      # buy | hold | sell
    forecast_7d_low: float
    forecast_7d_high: float
    key_factors: list[str]
    risks: list[str]
    summary: str


def _build_prompt(
    price: PriceSnapshot,
    signals: TechnicalSignals,
    news: list[NewsItem],
    cot: COTSnapshot,
) -> str:
    news_section = "\n".join(
        f"{i + 1}. [{item['source']}] {item['title']}\n   {item['summary'][:200]}"
        for i, item in enumerate(news[:20])
    ) or "No gold-relevant news found in the last 48 hours."

    return f"""You are an expert gold market analyst with deep knowledge of macroeconomics, technical analysis, and institutional positioning. Analyze the following data and provide a structured forecast and trading recommendation for gold (XAU/USD).

## Current Gold Price Data
- Spot price (USD/oz): ${price['current']:,.2f}
- 24h change: {price['change_pct_24h']:+.2f}% (${price['change_24h']:+.2f})
- 7-day change: {price['change_7d_pct']:+.2f}%
- 30-day change: {price['change_30d_pct']:+.2f}%
- 52-week range: ${price['low_52w']:,.2f} – ${price['high_52w']:,.2f}

## Technical Indicators
- RSI (14): {signals['rsi_14']} → {signals['rsi_signal']}
- MA20: ${signals['ma_20']:,.2f} (price is {signals['price_vs_ma20_pct']:+.2f}% vs MA20)
- MA50: ${signals['ma_50']:,.2f} (price is {signals['price_vs_ma50_pct']:+.2f}% vs MA50)
- MA200: ${signals['ma_200']:,.2f} (price is {signals['price_vs_ma200_pct']:+.2f}% vs MA200)
- Short-term trend: {signals['ma20_trend']}
- 7-day momentum: {signals['momentum_signal']}

## CFTC Commitments of Traders (week of {cot['report_date']})
- Speculative (non-commercial) net: {cot['noncomm_net']:+,} contracts
  - Long: {cot['noncomm_long']:,} | Short: {cot['noncomm_short']:,}
  - Week-over-week change: {cot['net_change_week']:+,} contracts
- Commercial (hedger) net: {cot['comm_net']:+,} contracts
- Open interest: {cot['open_interest']:,} contracts

## Recent Market News ({len(news)} items, last 48h)
{news_section}

---
Respond with ONLY a valid JSON object — no markdown fences, no commentary, just raw JSON:
{{
  "price_outlook": "<bullish|neutral|bearish>",
  "confidence": <integer 0-100>,
  "recommendation": "<buy|hold|sell>",
  "forecast_7d_low": <float>,
  "forecast_7d_high": <float>,
  "key_factors": ["<factor1>", "<factor2>", "<factor3>"],
  "risks": ["<risk1>", "<risk2>"],
  "summary": "<2-3 sentence narrative>"
}}"""


def _extract_json(text: str) -> dict:
    """Parse the first JSON object found in a text string."""
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]+\}", stripped)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No valid JSON found in LLM response:\n{stripped[:500]}")


def analyze(
    price: PriceSnapshot,
    signals: TechnicalSignals,
    news: list[NewsItem],
    cot: COTSnapshot,
) -> GoldRecommendation:
    """Call Claude claude-opus-4-6 with adaptive thinking to produce a gold recommendation."""
    client = anthropic.Anthropic()
    prompt = _build_prompt(price, signals, news, cot)

    log.info("Calling %s with adaptive thinking...", MODEL)

    # Stream to avoid HTTP timeouts; adaptive thinking may use variable token counts
    with client.messages.stream(
        model=MODEL,
        max_tokens=8192,
        thinking={"type": "adaptive"},
        system=(
            "You are a gold market analyst. "
            "Always respond with valid JSON only — no markdown, no explanation, just the JSON object."
        ),
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        final = stream.get_final_message()

    text_block = next((b for b in final.content if b.type == "text"), None)
    if text_block is None:
        raise RuntimeError("Claude returned no text block in response")

    raw = _extract_json(text_block.text)

    return {
        "price_outlook": str(raw.get("price_outlook", "neutral")),
        "confidence": int(raw.get("confidence", 50)),
        "recommendation": str(raw.get("recommendation", "hold")),
        "forecast_7d_low": float(raw.get("forecast_7d_low", price["current"] * 0.98)),
        "forecast_7d_high": float(raw.get("forecast_7d_high", price["current"] * 1.02)),
        "key_factors": list(raw.get("key_factors", [])),
        "risks": list(raw.get("risks", [])),
        "summary": str(raw.get("summary", "")),
    }
