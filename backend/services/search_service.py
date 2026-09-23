"""Web search using DuckDuckGo (no API key required) + optional SerpAPI."""
import httpx
import json
import re
import structlog
from urllib.parse import urlencode, quote_plus
from backend.config import get_settings

logger = structlog.get_logger()

_DDG_ENDPOINT = "https://api.duckduckgo.com/"
_DDG_HTML_ENDPOINT = "https://html.duckduckgo.com/html/"


async def search_web(query: str, max_results: int = 10) -> list[dict]:
    """
    Search the web via DuckDuckGo.
    Returns list of {title, url, snippet}.
    """
    settings = get_settings()

    # Try SerpAPI first if configured
    if settings.search_provider == "serpapi" and settings.serpapi_key:
        return await _serpapi_search(query, max_results)

    return await _ddg_search(query, max_results)


async def _ddg_search(query: str, max_results: int = 10) -> list[dict]:
    """DuckDuckGo search via HTML endpoint."""
    results = []

    # DDG HTML endpoint — more reliable than instant API for real web results
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(
                _DDG_HTML_ENDPOINT,
                params={"q": query},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
            )
            if r.status_code == 200:
                from bs4 import BeautifulSoup
                from urllib.parse import unquote, parse_qs, urlparse
                soup = BeautifulSoup(r.text, "html.parser")
                for result_div in soup.select(".result__body, .result")[:max_results * 2]:
                    title_el = result_div.select_one(".result__title a, .result__a")
                    snippet_el = result_div.select_one(".result__snippet")
                    if title_el:
                        url = title_el.get("href", "")
                        if "uddg=" in url:
                            parsed = parse_qs(urlparse(url).query)
                            url = unquote(parsed.get("uddg", [url])[0])
                        if url and url.startswith(("http://", "https://")) and "duckduckgo.com/y.js" not in url:
                            results.append({
                                "title": title_el.get_text(strip=True),
                                "url": url,
                                "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                                "source": "duckduckgo",
                            })
                        if len(results) >= max_results:
                            break
            else:
                logger.warning("ddg.bad_status", status=r.status_code)
    except Exception as e:
        logger.warning("ddg.search_failed", error=str(e))

    # Fallback: DDG instant API for topic pages
    if not results:
        try:
            params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(_DDG_ENDPOINT, params=params,
                                      headers={"User-Agent": "FRONTIER-Bot/1.0"})
                if r.status_code == 200:
                    data = r.json()
                    for item in data.get("RelatedTopics", [])[:max_results]:
                        if "FirstURL" in item and "Text" in item:
                            results.append({
                                "title": item["Text"][:120],
                                "url": item["FirstURL"],
                                "snippet": item["Text"],
                                "source": "duckduckgo",
                            })
        except Exception as e:
            logger.warning("ddg.instant_api_failed", error=str(e))

    logger.info("search.complete", query=query[:50], results=len(results))
    return results[:max_results]


async def _serpapi_search(query: str, max_results: int = 10) -> list[dict]:
    settings = get_settings()
    try:
        params = {
            "q": query,
            "api_key": settings.serpapi_key,
            "num": max_results,
            "engine": "google",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get("https://serpapi.com/search", params=params)
            r.raise_for_status()
            data = r.json()
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": "serpapi",
            }
            for item in data.get("organic_results", [])[:max_results]
        ]
    except Exception as e:
        logger.warning("serpapi.failed", error=str(e))
        return await _ddg_search(query, max_results)


async def search_hackathons(max_results: int = 15) -> list[dict]:
    """Search for active hackathons from multiple sources."""
    queries = [
        "hackathon 2025 2026 student registration open",
        "devpost hackathon site:devpost.com upcoming",
        "MLH hackathon schedule site:mlh.io",
    ]
    all_results = []
    for q in queries:
        results = await search_web(q, max_results=5)
        all_results.extend(results)

    # Deduplicate by URL
    seen = set()
    deduped = []
    for r in all_results:
        url = r.get("url", "")
        if url and url not in seen:
            seen.add(url)
            deduped.append(r)

    return deduped[:max_results]


async def search_research(query: str, max_results: int = 10) -> list[dict]:
    """Search arXiv and research sources."""
    from backend.services.arxiv_service import search_arxiv
    arxiv_results = await search_arxiv(query, max_results=5)
    web_results = await search_web(f"research paper {query} site:arxiv.org OR site:papers.with.code", max_results=5)
    combined = arxiv_results + web_results
    seen = set()
    deduped = []
    for r in combined:
        url = r.get("url", "")
        if url and url not in seen:
            seen.add(url)
            deduped.append(r)
    return deduped[:max_results]
