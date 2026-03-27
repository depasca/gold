# gold-intel

Automated gold market intelligence pipeline. Fetches price data, institutional positioning, and news daily — then produces a price forecast and buy/hold/sell recommendation via Claude LLM or a lightweight rule-based engine.

## Features

- **Two analysis modes:** LLM-powered (Claude claude-opus-4-6 with adaptive thinking) or instant rule-based scoring
- **Price data:** COMEX gold futures (GC=F) via Yahoo Finance — 1-year history, RSI, MA20/50/200, momentum
- **Institutional positioning:** CFTC Commitments of Traders (public API, no key needed)
- **News:** 5 RSS feeds (Kitco, Reuters, Mining.com, MarketWatch, goldprice.org), keyword-filtered
- **Reports:** timestamped Markdown + JSON saved to `reports/`
- **Cron-ready:** single script entry point, logs to stdout

## Quick start

```bash
# 1. Clone and set up
git clone <repo>
cd gold
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Add your ANTHROPIC_API_KEY (only needed for --mode=api)

# 3. Run
.venv/bin/python main.py --mode=light   # rule-based, instant, free
.venv/bin/python main.py --mode=api     # Claude LLM analysis (default)
```

## Analysis modes

| Flag | Engine | API key | Cost | Speed |
|------|--------|---------|------|-------|
| `--mode=api` | Claude claude-opus-4-6 (adaptive thinking) | Required | ~$0.06/run | ~15–30s |
| `--mode=light` | Rule-based scoring | Not needed | Free | ~3–5s |

## Output

Each run writes two files to `reports/`:

```
reports/2026-03-27T06-00-00Z.md    ← human-readable report
reports/2026-03-27T06-00-00Z.json  ← structured data
```

The report includes current price, technical signals, COT positioning, key factors, risks, 7-day price forecast, and a buy/hold/sell recommendation with confidence score.

## Scheduling (daily at 06:00 UTC)

```cron
0 6 * * * /path/to/gold/.venv/bin/python /path/to/gold/main.py >> /path/to/gold/gold.log 2>&1
```

## Project structure

```
gold/
├── main.py                    # entry point — argparse, orchestration
├── requirements.txt
├── .env.example
├── reports/                   # generated reports (gitignored)
└── src/
    ├── fetchers/
    │   ├── price.py           # yfinance → PriceSnapshot
    │   ├── news.py            # RSS feeds → list[NewsItem]
    │   └── cot.py             # CFTC Socrata API → COTSnapshot
    ├── analysis/
    │   ├── types.py           # GoldRecommendation TypedDict
    │   ├── signals.py         # RSI/MA/momentum → TechnicalSignals
    │   ├── llm.py             # Claude API → GoldRecommendation
    │   └── rules.py           # rule-based scoring → GoldRecommendation
    └── report.py              # save JSON + Markdown to reports/
```

## Data sources

All free and public — no API keys except Anthropic (only for `--mode=api`):

| Source | Data | API key |
|--------|------|---------|
| Yahoo Finance (`yfinance`) | Gold futures price + history | No |
| CFTC public Socrata API | Commitments of Traders | No |
| RSS feeds (5 sources) | Market news | No |
| Anthropic (`claude-opus-4-6`) | LLM analysis | Yes (`--mode=api` only) |

## Light mode scoring

The rule-based engine scores three signal groups:

- **Technical** (±58 pts): RSI level, price vs MA50/200, 7-day momentum, MA20 trend
- **COT** (±10 pts): week-over-week change in speculative net position
- **News** (±15 pts): keyword count of bullish vs bearish terms in headlines

Score ≥ 20 → **buy**, ≤ −20 → **sell**, else → **hold**. Confidence = `min(90, 50 + abs(score) / 2)`.

## Cost estimate (`--mode=api`)

~$0.05–0.06 per run · ~$1.80/month · ~$22/year at one run per day.
