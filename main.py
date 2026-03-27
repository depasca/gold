#!/usr/bin/env python3
"""Gold market intelligence pipeline — cron entry point.

Run manually:
    python main.py              # API mode (Claude LLM, default)
    python main.py --mode=api   # same as above
    python main.py --mode=light # rule-based scoring, no API key needed

Add to crontab for daily execution at 06:00 UTC:
    0 6 * * * /path/to/gold/.venv/bin/python /path/to/gold/main.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from src.analysis.signals import compute_signals
from src.fetchers.cot import COTSnapshot, fetch_cot
from src.fetchers.news import fetch_news
from src.fetchers.price import fetch_price
from src.report import save_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("gold")

_EMPTY_COT: COTSnapshot = {
    "report_date": "unavailable",
    "open_interest": 0,
    "noncomm_long": 0,
    "noncomm_short": 0,
    "noncomm_net": 0,
    "comm_long": 0,
    "comm_short": 0,
    "comm_net": 0,
    "net_change_week": 0,
    "weeks_available": 0,
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gold market intelligence pipeline")
    parser.add_argument(
        "--mode",
        choices=["api", "light"],
        default="api",
        help="Analysis mode: 'api' uses Claude LLM (default), 'light' uses rule-based scoring",
    )
    return parser.parse_args()


def run(mode: str) -> None:
    log.info("=== Gold intelligence pipeline starting (mode=%s) ===", mode)

    log.info("Fetching gold price...")
    price = fetch_price()
    log.info(
        "Gold spot: $%,.2f  |  24h: %+.2f%%  |  7d: %+.2f%%",
        price["current"],
        price["change_pct_24h"],
        price["change_7d_pct"],
    )

    log.info("Fetching news...")
    news = fetch_news()
    log.info("Collected %d gold-relevant news items", len(news))

    log.info("Fetching CFTC COT data...")
    try:
        cot = fetch_cot()
        log.info(
            "COT week %s  |  Spec. net: %+,d  |  WoW: %+,d",
            cot["report_date"],
            cot["noncomm_net"],
            cot["net_change_week"],
        )
    except Exception as exc:
        log.warning("COT fetch failed (%s) — proceeding without positioning data", exc)
        cot = _EMPTY_COT

    log.info("Computing technical signals...")
    signals = compute_signals(price)
    log.info(
        "RSI: %.1f (%s)  |  vs MA50: %+.2f%%  |  Momentum: %s",
        signals["rsi_14"],
        signals["rsi_signal"],
        signals["price_vs_ma50_pct"],
        signals["momentum_signal"],
    )

    if mode == "light":
        log.info("Running rule-based scoring (light mode)...")
        from src.analysis.rules import score as analyze_fn
    else:
        log.info("Running LLM analysis (Claude claude-opus-4-6)...")
        from src.analysis.llm import analyze as analyze_fn  # type: ignore[assignment]

    rec = analyze_fn(price, signals, news, cot)
    log.info(
        "Recommendation: %s  |  Outlook: %s  |  Confidence: %d%%  |  7d: $%,.0f – $%,.0f",
        rec["recommendation"].upper(),
        rec["price_outlook"],
        rec["confidence"],
        rec["forecast_7d_low"],
        rec["forecast_7d_high"],
    )

    report_path = save_report(price, signals, news, cot, rec)
    log.info("Report → %s", report_path)
    log.info("=== Pipeline complete ===")


if __name__ == "__main__":
    args = _parse_args()
    try:
        run(args.mode)
    except Exception:
        log.exception("Pipeline failed")
        sys.exit(1)
