"""Generate and persist gold market reports as JSON + Markdown."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.analysis.types import GoldRecommendation
from src.analysis.signals import TechnicalSignals
from src.fetchers.cot import COTSnapshot
from src.fetchers.news import NewsItem
from src.fetchers.price import PriceSnapshot

log = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).parent.parent / "reports"

_OUTLOOK = {"bullish": "▲ Bullish", "neutral": "→ Neutral", "bearish": "▼ Bearish"}
_REC = {"buy": "BUY", "hold": "HOLD", "sell": "SELL"}


def _markdown(
    ts: str,
    price: PriceSnapshot,
    signals: TechnicalSignals,
    cot: COTSnapshot,
    news: list[NewsItem],
    rec: GoldRecommendation,
) -> str:
    factors = "\n".join(f"- {f}" for f in rec["key_factors"])
    risks = "\n".join(f"- {r}" for r in rec["risks"])
    news_lines = "\n".join(
        f"- **[{item['source']}]** {item['title']}" for item in news[:12]
    )
    outlook_label = _OUTLOOK.get(rec["price_outlook"], rec["price_outlook"].title())
    rec_label = _REC.get(rec["recommendation"], rec["recommendation"].upper())

    return f"""# Gold Market Intelligence Report
**Generated:** {ts} UTC

---

## Recommendation: {rec_label} (confidence: {rec['confidence']}%)
**Outlook:** {outlook_label}
**7-day price range forecast:** ${rec['forecast_7d_low']:,.2f} – ${rec['forecast_7d_high']:,.2f}

---

## Current Price
| Metric | Value |
|--------|-------|
| Spot (USD/oz) | **${price['current']:,.2f}** |
| 24h change | {price['change_pct_24h']:+.2f}% (${price['change_24h']:+.2f}) |
| 7-day change | {price['change_7d_pct']:+.2f}% |
| 30-day change | {price['change_30d_pct']:+.2f}% |
| 52-week range | ${price['low_52w']:,.2f} – ${price['high_52w']:,.2f} |

---

## Technical Signals
| Indicator | Value | Signal |
|-----------|-------|--------|
| RSI (14) | {signals['rsi_14']} | {signals['rsi_signal'].title()} |
| MA20 | ${signals['ma_20']:,.2f} | {signals['price_vs_ma20_pct']:+.2f}% from price |
| MA50 | ${signals['ma_50']:,.2f} | {signals['price_vs_ma50_pct']:+.2f}% from price |
| MA200 | ${signals['ma_200']:,.2f} | {signals['price_vs_ma200_pct']:+.2f}% from price |
| Trend (MA20) | — | {signals['ma20_trend'].title()} |
| Momentum (7d) | — | {signals['momentum_signal'].replace('_', ' ').title()} |

---

## Institutional Positioning (COT — week of {cot['report_date']})
| Category | Long | Short | Net |
|----------|------|-------|-----|
| Speculative | {cot['noncomm_long']:,} | {cot['noncomm_short']:,} | {cot['noncomm_net']:+,} |
| Commercial | {cot['comm_long']:,} | {cot['comm_short']:,} | {cot['comm_net']:+,} |

**Week-over-week speculative net change:** {cot['net_change_week']:+,} contracts
**Open interest:** {cot['open_interest']:,} contracts

---

## Key Factors
{factors}

## Risks
{risks}

## Analysis
{rec['summary']}

---

## Recent News
{news_lines}

---
*Powered by Claude {rec.get('_model', 'claude-opus-4-6')} · CFTC COT · Yahoo Finance · RSS*
"""


def save_report(
    price: PriceSnapshot,
    signals: TechnicalSignals,
    news: list[NewsItem],
    cot: COTSnapshot,
    rec: GoldRecommendation,
) -> Path:
    """Persist JSON + Markdown reports; returns the Markdown path."""
    REPORTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")

    payload = {
        "generated_at": ts,
        "price": price,
        "signals": signals,
        "cot": cot,
        "recommendation": rec,
        "news_count": len(news),
    }

    json_path = REPORTS_DIR / f"{ts}.json"
    json_path.write_text(json.dumps(payload, indent=2, default=str))

    md_path = REPORTS_DIR / f"{ts}.md"
    md_path.write_text(_markdown(ts, price, signals, cot, news, rec))

    log.info("Saved: %s  |  %s", json_path.name, md_path.name)
    return md_path
