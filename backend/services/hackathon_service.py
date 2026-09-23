"""Hackathon discovery — Devpost API, MLH, Unstop, Devfolio, web search fallback."""
import httpx
import re
import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "en-US,en;q=0.5",
}


async def fetch_devpost_hackathons(max_items: int = 20) -> list[dict]:
    """Fetch open hackathons from Devpost JSON API."""
    results: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(
                "https://devpost.com/api/hackathons",
                params={"status[]": "open", "order_by": "deadline", "page": 1},
                headers={**HEADERS, "Accept": "application/json"},
            )
            if r.status_code == 200:
                for h in r.json().get("hackathons", [])[:max_items]:
                    deadline = h.get("submission_period_dates", "")
                    results.append({
                        "title": h.get("title", ""),
                        "url": h.get("url", ""),
                        "snippet": (
                            f"Prize: {h.get('prize_amount', 'N/A')} | "
                            f"Participants: {h.get('registrations_count', '?')} | "
                            f"Deadline: {deadline}"
                        ),
                        "prize": h.get("prize_amount", ""),
                        "deadline": deadline,
                        "source": "devpost",
                        "category": "HACKATHON",
                    })
                logger.info("hackathon.devpost_api", count=len(results))
                return results
    except Exception as e:
        logger.warning("hackathon.devpost_api_failed", error=str(e))

    # HTML fallback
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=HEADERS) as client:
            r = await client.get("https://devpost.com/hackathons?status[]=open&order_by=deadline")
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for tile in soup.select(".hackathon-tile, article.hackathon")[:max_items]:
                    title_el = tile.select_one("h3, h2, .title")
                    link_el = tile.select_one("a[href]")
                    if not (title_el and link_el):
                        continue
                    href = link_el.get("href", "")
                    if not href.startswith("http"):
                        href = "https://devpost.com" + href
                    snippet_el = tile.select_one(".tagline, p")
                    results.append({
                        "title": title_el.get_text(strip=True),
                        "url": href,
                        "snippet": snippet_el.get_text(strip=True)[:300] if snippet_el else "",
                        "source": "devpost",
                        "category": "HACKATHON",
                    })
        logger.info("hackathon.devpost_html", count=len(results))
    except Exception as e:
        logger.warning("hackathon.devpost_html_failed", error=str(e))

    return results


async def fetch_mlh_hackathons(max_items: int = 20) -> list[dict]:
    """Scrape upcoming hackathons from MLH via Inertia.js JSON payload."""
    import json as _json
    results: list[dict] = []
    urls_to_try = [
        "https://mlh.io/seasons/2026/events",
        "https://mlh.io/seasons/2025/events",
        "https://mlh.io/events",
    ]
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=HEADERS) as client:
            for url in urls_to_try:
                r = await client.get(url)
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                script = soup.select_one("script[data-page]")
                if not script:
                    continue
                page_data = _json.loads(script.string or "{}")
                # Walk props to find the events list (depth-2 list with id/slug/name)
                events = _find_events_list(page_data.get("props", {}))
                for ev in events:
                    status = ev.get("status", "")
                    if status == "ended":
                        continue
                    name = ev.get("name", "")
                    slug = ev.get("slug", "")
                    ev_url = ev.get("url", "")
                    if ev_url and not ev_url.startswith("http"):
                        ev_url = "https://mlh.io" + ev_url
                    date_range = ev.get("dateRange", "")
                    location = ev.get("location", ev.get("city", ""))
                    if name and ev_url:
                        results.append({
                            "title": name,
                            "url": ev_url,
                            "snippet": f"Date: {date_range} | Location: {location} | Status: {status}",
                            "deadline": ev.get("endsAt", ""),
                            "source": "mlh",
                            "category": "HACKATHON",
                        })
                    if len(results) >= max_items:
                        break
                if results:
                    break
        logger.info("hackathon.mlh", count=len(results))
    except Exception as e:
        logger.warning("hackathon.mlh_failed", error=str(e))
    return results


def _find_events_list(obj, depth: int = 0) -> list:
    """Recursively find first list of dicts with hackathon-like keys."""
    if depth > 4:
        return []
    if isinstance(obj, list) and len(obj) > 2:
        first = obj[0] if obj else {}
        if isinstance(first, dict) and ("slug" in first or "startsAt" in first):
            return obj
    if isinstance(obj, dict):
        for v in obj.values():
            found = _find_events_list(v, depth + 1)
            if found:
                return found
    return []


async def fetch_unstop_hackathons(max_items: int = 15) -> list[dict]:
    """Fetch hackathons from Unstop (Indian competitions platform)."""
    results: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            # Unstop public API endpoint
            r = await client.get(
                "https://unstop.com/api/public/opportunity/search-new",
                params={
                    "type": "hackathon",
                    "per_page": max_items,
                },
                headers={**HEADERS, "Accept": "application/json", "Referer": "https://unstop.com/"},
            )
            if r.status_code == 200:
                data = r.json()
                raw = data.get("data", {})
                items = raw.get("data", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
                for item in items[:max_items]:
                    title = item.get("title") or item.get("name", "")
                    url = f"https://unstop.com/{item.get('public_url', '')}" if item.get("public_url") else "https://unstop.com/hackathons"
                    deadline = item.get("end_date") or item.get("deadline", "")
                    prize = item.get("prize_money") or item.get("prizes", "")
                    org = item.get("organisation", {}).get("name", "") if isinstance(item.get("organisation"), dict) else ""
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": f"Organizer: {org} | Deadline: {deadline} | Prize: {prize}",
                        "deadline": str(deadline),
                        "source": "unstop",
                        "category": "HACKATHON",
                    })
                logger.info("hackathon.unstop_api", count=len(results))
                return results
    except Exception as e:
        logger.warning("hackathon.unstop_api_failed", error=str(e))

    # HTML fallback — scrape listing page
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=HEADERS) as client:
            r = await client.get("https://unstop.com/hackathons")
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for card in soup.select(".opportunity-card, .card, [class*='card']")[:max_items]:
                    title_el = card.select_one("h2, h3, .title, [class*='title']")
                    link_el = card.select_one("a[href]")
                    date_el = card.select_one("[class*='date'], [class*='deadline'], time")
                    if not title_el or not link_el:
                        continue
                    href = link_el.get("href", "")
                    if href and not href.startswith("http"):
                        href = "https://unstop.com" + href
                    results.append({
                        "title": title_el.get_text(strip=True),
                        "url": href,
                        "snippet": f"Deadline: {date_el.get_text(strip=True) if date_el else 'See website'}",
                        "source": "unstop",
                        "category": "HACKATHON",
                    })
        logger.info("hackathon.unstop_html", count=len(results))
    except Exception as e:
        logger.warning("hackathon.unstop_html_failed", error=str(e))

    return results


async def fetch_devfolio_hackathons(max_items: int = 10) -> list[dict]:
    """Fetch hackathons from Devfolio."""
    results: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(
                "https://devfolio.co/api/search/hackathons",
                params={"q": "", "is_open": "true", "limit": max_items},
                headers={**HEADERS, "Accept": "application/json"},
            )
            if r.status_code == 200:
                data = r.json()
                items = data.get("results", data.get("hackathons", []))
                for h in items[:max_items]:
                    slug = h.get("slug", "")
                    results.append({
                        "title": h.get("name", ""),
                        "url": f"https://{slug}.devfolio.co" if slug else "https://devfolio.co/hackathons",
                        "snippet": (
                            f"Deadline: {h.get('submission_deadline', 'TBA')} | "
                            f"Prize: {h.get('prize_pool', 'N/A')}"
                        ),
                        "deadline": h.get("submission_deadline", ""),
                        "source": "devfolio",
                        "category": "HACKATHON",
                    })
                logger.info("hackathon.devfolio", count=len(results))
    except Exception as e:
        logger.warning("hackathon.devfolio_failed", error=str(e))
    return results


async def discover_hackathons(max_items: int = 25) -> list[dict]:
    """Aggregate hackathons from all sources, deduplicated."""
    from backend.services.search_service import search_web

    devpost = await fetch_devpost_hackathons(max_items=12)
    mlh = await fetch_mlh_hackathons(max_items=8)
    unstop = await fetch_unstop_hackathons(max_items=10)
    devfolio = await fetch_devfolio_hackathons(max_items=8)

    # Web search fallback for any gaps
    search_results = await search_web(
        "student hackathon 2025 2026 open registration AI devpost mlh",
        max_results=6,
    )
    search_mapped = [
        {**r, "category": "HACKATHON", "source": "search"}
        for r in search_results
        if "unstop.com/hackathons" not in r.get("url", "")  # skip listing pages
    ]

    all_items = devpost + mlh + unstop + devfolio + search_mapped

    # URLs that are listing pages, not individual hackathons
    LISTING_PAGES = {
        "https://unstop.com/hackathons",
        "https://devpost.com/hackathons",
        "https://mlh.io/events",
        "https://devfolio.co/hackathons",
    }

    # Deduplicate by URL, skip listing pages
    seen: set[str] = set()
    deduped: list[dict] = []
    for item in all_items:
        url = item.get("url", "").rstrip("/").lower()
        if not url or url in LISTING_PAGES:
            continue
        if url not in seen:
            seen.add(url)
            deduped.append(item)

    logger.info("hackathon.combined", total=len(deduped))
    return deduped[:max_items]
