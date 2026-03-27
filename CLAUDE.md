# gold-intel — project context for Claude

## What this is
Automated gold market intelligence pipeline. Runs daily via cron. Fetches price, news, and institutional positioning data, then produces a buy/hold/sell recommendation and 7-day price forecast.

## Entry point
```bash
.venv/bin/python main.py --mode=light   # rule-based, no API key
.venv/bin/python main.py --mode=api     # Claude LLM (default)
```

## Architecture

```
main.py
  ├── fetch_price()      → PriceSnapshot         (yfinance GC=F, 1y history)
  ├── fetch_news()       → list[NewsItem]         (5 RSS feeds, keyword-filtered)
  ├── fetch_cot()        → COTSnapshot            (CFTC Socrata API, no key)
  ├── compute_signals()  → TechnicalSignals       (RSI14, MA20/50/200, momentum)
  ├── analyze() OR score() → GoldRecommendation  (mode=api or mode=light)
  └── save_report()      → reports/TIMESTAMP.{json,md}
```

## Key files

| File | Purpose |
|------|---------|
| `main.py` | Orchestrator, argparse (`--mode api\|light`), lazy imports per mode |
| `src/analysis/types.py` | `GoldRecommendation` TypedDict (shared by both modes) |
| `src/analysis/llm.py` | `analyze()` — Claude claude-opus-4-6, adaptive thinking, streaming |
| `src/analysis/rules.py` | `score()` — deterministic scoring, no API, same return type |
| `src/analysis/signals.py` | `compute_signals(price) → TechnicalSignals` |
| `src/fetchers/price.py` | `fetch_price() → PriceSnapshot` |
| `src/fetchers/news.py` | `fetch_news() → list[NewsItem]` |
| `src/fetchers/cot.py` | `fetch_cot() → COTSnapshot` |
| `src/report.py` | `save_report(price, signals, news, cot, rec) → Path` |

## TypedDicts

- `PriceSnapshot` — current, change_pct_24h/7d/30d, high/low_52w, history_30d, closes_1y
- `TechnicalSignals` — rsi_14, ma_20/50/200, price_vs_ma*_pct, ma20_trend, rsi_signal, momentum_signal
- `COTSnapshot` — noncomm/comm long/short/net, net_change_week, open_interest, report_date
- `NewsItem` — title, summary, source, published, url
- `GoldRecommendation` — price_outlook, confidence, recommendation, forecast_7d_low/high, key_factors, risks, summary

## Rules for `score()` (light mode)
Technical (±58): RSI ±15, vs MA50 ±10, vs MA200 ±5, momentum ±20, trend ±8
COT (±10): net_change_week buckets (>2000/0/<0/<-2000)
News (±15): (bullish_kw_hits − bearish_kw_hits) × 3, clamped
Score ≥20 → buy, ≤−20 → sell, else hold. Confidence = min(90, 50 + abs(score)//2).

## Environment
- Python 3.13, venv at `.venv/`
- `ANTHROPIC_API_KEY` in `.env` — only required for `--mode=api`
- `ANTHROPIC_MODEL` env var overrides model (default: `claude-opus-4-6`)

## Dependencies
`anthropic`, `yfinance`, `feedparser`, `requests`, `python-dotenv`, `pandas`, `numpy`
No new dependencies without approval.

## Code conventions
- Strongly typed throughout (TypedDicts, type hints)
- Functional style — no classes unless justified
- Both `analyze()` and `score()` have identical signatures; `main.py` uses lazy imports to avoid loading `anthropic` in light mode

## Reports
Saved to `reports/YYYY-MM-DDTHH-MM-SSZ.{json,md}`. Gitignored. The `reports/` dir is created at runtime if absent.
