"""
X (Twitter) API v2 integration.

Uses Bearer Token only (app-level, read-only search).
No user OAuth. No passwords. No browser automation.
Only reads public posts.
"""
import httpx
import structlog
from backend.config import get_settings

logger = structlog.get_logger()

X_API_BASE = "https://api.twitter.com/2"

SEARCH_QUERIES = {
    "AI": [
        "(AI OR LLM OR \"language model\") (open source OR released OR tutorial) -is:retweet lang:en",
        "(Ollama OR HuggingFace OR vibe coding) (new OR released) -is:retweet lang:en",
    ],
    "BUILD": [
        "(github.com OR open source) (python OR typescript OR react) (released OR launched) -is:retweet lang:en",
    ],
    "RESEARCH": [
        "(arxiv.org OR \"new paper\" OR \"research paper\") (AI OR ML OR \"machine learning\") -is:retweet lang:en",
    ],
    "HACKATHON": [
        "(hackathon OR \"coding competition\") (registration OR open OR deadline) -is:retweet lang:en",
    ],
    "OPPORTUNITY": [
        "(internship OR fellowship) (AI OR \"machine learning\" OR software) students -is:retweet lang:en",
    ],
}

TWEET_FIELDS = "id,text,created_at,author_id,public_metrics,entities"
EXPANSIONS = "author_id"
USER_FIELDS = "name,username,verified"


async def search_x(
    query: str,
    max_results: int = 20,
    days_back: int = 7,
) -> list[dict]:
    """
    Search X for recent public tweets matching query.
    Requires BEARER_TOKEN in .env.
    """
    settings = get_settings()
    if not settings.x_bearer_token:
        logger.warning("x.no_bearer_token")
        return []

    from datetime import datetime, timezone, timedelta
    start_time = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")

    params = {
        "query": query,
        "max_results": min(max_results, 100),
        "tweet.fields": TWEET_FIELDS,
        "expansions": EXPANSIONS,
        "user.fields": USER_FIELDS,
        "start_time": start_time,
        "sort_order": "relevancy",
    }

    headers = {
        "Authorization": f"Bearer {settings.x_bearer_token}",
        "User-Agent": "FRONTIER-Bot/1.0",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{X_API_BASE}/tweets/search/recent",
                params=params,
                headers=headers,
            )
            if r.status_code == 401:
                logger.error("x.unauthorized", msg="Check X_BEARER_TOKEN in .env")
                return []
            if r.status_code == 429:
                logger.warning("x.rate_limited")
                return []
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as e:
        logger.warning("x.http_error", status=e.response.status_code)
        return []
    except Exception as e:
        logger.warning("x.search_failed", error=str(e))
        return []

    tweets = data.get("data", [])
    includes = data.get("includes", {})
    users = {u["id"]: u for u in includes.get("users", [])}

    results = []
    for tweet in tweets:
        author = users.get(tweet.get("author_id", ""), {})
        metrics = tweet.get("public_metrics", {})
        entities = tweet.get("entities", {})

        # Extract URLs from tweet entities
        urls = [
            u.get("expanded_url", u.get("url", ""))
            for u in entities.get("urls", [])
            if not u.get("expanded_url", "").startswith("https://t.co")
        ]

        results.append({
            "title": tweet["text"][:120],
            "url": urls[0] if urls else f"https://twitter.com/i/web/status/{tweet['id']}",
            "snippet": tweet["text"],
            "author": f"@{author.get('username', 'unknown')}",
            "author_verified": author.get("verified", False),
            "likes": metrics.get("like_count", 0),
            "retweets": metrics.get("retweet_count", 0),
            "created_at": tweet.get("created_at", ""),
            "tweet_id": tweet["id"],
            "source": "x",
            "category": "GENERAL",
        })

    logger.info("x.search_complete", query=query[:50], results=len(results))
    return results


async def discover_x_by_category(
    category: str,
    max_results: int = 15,
    days_back: int = 7,
) -> list[dict]:
    """Run X searches for a content category."""
    queries = SEARCH_QUERIES.get(category.upper(), [])
    all_results: list[dict] = []
    seen_ids: set[str] = set()

    for query in queries:
        tweets = await search_x(query, max_results=max_results // len(queries) + 2, days_back=days_back)
        for t in tweets:
            tid = t.get("tweet_id", "")
            if tid not in seen_ids:
                seen_ids.add(tid)
                t["category"] = category.upper()
                all_results.append(t)

    return all_results[:max_results]


async def health_check() -> bool:
    settings = get_settings()
    if not settings.x_bearer_token:
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                f"{X_API_BASE}/tweets/search/recent",
                params={"query": "test", "max_results": 10},
                headers={"Authorization": f"Bearer {settings.x_bearer_token}"},
            )
            return r.status_code in (200, 400)  # 400 = bad query but auth OK
    except Exception:
        return False
