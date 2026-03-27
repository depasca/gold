"""Fetch gold-relevant news from public RSS feeds (no API key required)."""

from __future__ import annotations

import logging
import re
from typing import TypedDict

import feedparser

log = logging.getLogger(__name__)

RSS_FEEDS: list[str] = [
    "https://www.kitco.com/rss/",          # dedicated gold news
    "https://goldprice.org/feed",           # gold price commentary
    "https://feeds.reuters.com/reuters/businessNews",
    "https://www.mining.com/feed/",         # mining / metals
    "https://www.marketwatch.com/rss/topstories",
]

# Keywords that signal gold-relevant content (macro factors included)
GOLD_KEYWORDS: frozenset[str] = frozenset(
    {
        "gold", "xau", "bullion", "precious metal",
        "comex", "federal reserve", "fed rate", "inflation",
        "interest rate", "dollar index", "usd index",
        "central bank", "safe haven", "geopolit",
        "treasury yield", "bond yield", "recession",
        "etf", "gld", "silver", "commodity",
        "monetary policy", "rate hike", "rate cut",
        "debt ceiling", "banking crisis",
    }
)


class NewsItem(TypedDict):
    title: str
    summary: str
    source: str
    published: str
    url: str


def _is_gold_relevant(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in GOLD_KEYWORDS)


def _clean_html(raw: str) -> str:
    return re.sub(r"<[^>]+>", "", raw).strip()


def _parse_entry(entry: feedparser.FeedParserDict, source: str) -> NewsItem | None:
    title = entry.get("title", "").strip()
    summary = _clean_html(entry.get("summary", entry.get("description", "")))[:600]

    if not title or not _is_gold_relevant(title + " " + summary):
        return None

    return {
        "title": title,
        "summary": summary,
        "source": source,
        "published": entry.get("published", entry.get("updated", "")),
        "url": entry.get("link", ""),
    }


def fetch_news(max_items: int = 30) -> list[NewsItem]:
    """Fetch and deduplicate gold-relevant news across all configured RSS feeds."""
    items: list[NewsItem] = []

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            source = feed.feed.get("title", url)
            for entry in feed.get("entries", [])[:25]:
                item = _parse_entry(entry, source)
                if item:
                    items.append(item)
        except Exception as exc:
            log.warning("Feed fetch failed [%s]: %s", url, exc)

    # Deduplicate by normalised title prefix
    seen: set[str] = set()
    unique: list[NewsItem] = []
    for item in items:
        key = item["title"].lower()[:80]
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique[:max_items]
