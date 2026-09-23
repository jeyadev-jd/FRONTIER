"""RSS/Atom feed reader for tech blogs and news sources."""
import feedparser
import hashlib
import httpx
import structlog
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

logger = structlog.get_logger()

DEFAULT_FEEDS = {
    "huggingface-blog": {
        "url": "https://huggingface.co/blog/feed.xml",
        "category": "AI",
        "label": "HuggingFace Blog",
    },
    "pytorch-blog": {
        "url": "https://pytorch.org/blog/feed.xml",
        "category": "AI",
        "label": "PyTorch Blog",
    },
    "paperswithcode": {
        "url": "https://paperswithcode.com/latest.xml",
        "category": "RESEARCH",
        "label": "Papers With Code",
    },
    "github-blog": {
        "url": "https://github.blog/feed/",
        "category": "BUILD",
        "label": "GitHub Blog",
    },
    "fastai": {
        "url": "https://www.fast.ai/index.xml",
        "category": "AI",
        "label": "fast.ai",
    },
    "google-ai-blog": {
        "url": "https://blog.google/technology/ai/rss/",
        "category": "AI",
        "label": "Google AI Blog",
    },
    "anthropic-news": {
        "url": "https://www.anthropic.com/news/rss.xml",
        "category": "AI",
        "label": "Anthropic News",
    },
    "openai-news": {
        "url": "https://openai.com/news/rss.xml",
        "category": "AI",
        "label": "OpenAI News",
    },
    "devpost-hackathons": {
        "url": "https://devpost.com/hackathons.atom",
        "category": "HACKATHON",
        "label": "Devpost Hackathons",
    },
}


def _parse_date(entry: dict) -> datetime | None:
    """Try to extract a publication date from a feed entry."""
    for field in ("published", "updated", "created"):
        raw = entry.get(field) or entry.get(f"{field}_parsed")
        if raw:
            if isinstance(raw, str):
                try:
                    return parsedate_to_datetime(raw).replace(tzinfo=timezone.utc)
                except Exception:
                    pass
            elif hasattr(raw, "tm_year"):
                try:
                    return datetime(*raw[:6], tzinfo=timezone.utc)
                except Exception:
                    pass
    return None


async def fetch_feed(url: str, max_items: int = 15, days_back: int = 30) -> list[dict]:
    """Fetch and parse an RSS/Atom feed. Returns list of normalized items."""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "FRONTIER-Bot/1.0 (feedreader)"})
            r.raise_for_status()
            content = r.text
    except Exception as e:
        logger.warning("rss.fetch_failed", url=url[:60], error=str(e))
        return []

    try:
        feed = feedparser.parse(content)
    except Exception as e:
        logger.warning("rss.parse_failed", url=url[:60], error=str(e))
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    results = []

    for entry in feed.entries[:max_items * 2]:
        title = (getattr(entry, "title", "") or "").strip()
        link = (getattr(entry, "link", "") or "").strip()
        summary = (getattr(entry, "summary", "") or
                   getattr(entry, "description", "") or "").strip()[:400]

        if not link or not link.startswith("http"):
            continue

        pub_date = _parse_date(dict(entry))
        if pub_date and pub_date < cutoff:
            continue

        results.append({
            "title": title,
            "url": link,
            "snippet": summary,
            "published": pub_date.isoformat() if pub_date else None,
            "source": "rss",
            "feed_url": url,
        })

        if len(results) >= max_items:
            break

    logger.info("rss.fetched", url=url[:60], items=len(results))
    return results


async def fetch_all_feeds(
    feeds: dict | None = None,
    category_filter: str | None = None,
    max_per_feed: int = 8,
    days_back: int = 14,
) -> list[dict]:
    """Fetch multiple configured feeds. Returns combined deduplicated list."""
    if feeds is None:
        feeds = DEFAULT_FEEDS

    all_items: list[dict] = []
    seen_urls: set[str] = set()

    for feed_id, cfg in feeds.items():
        if category_filter and cfg.get("category") != category_filter:
            continue
        items = await fetch_feed(cfg["url"], max_items=max_per_feed, days_back=days_back)
        for item in items:
            url = item["url"]
            if url not in seen_urls:
                seen_urls.add(url)
                item["feed_label"] = cfg.get("label", feed_id)
                item["category"] = cfg.get("category", "GENERAL")
                all_items.append(item)

    logger.info("rss.all_feeds_complete", total=len(all_items), category=category_filter)
    return all_items
