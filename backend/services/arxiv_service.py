"""arXiv paper discovery via their free Atom API."""
import httpx
import xml.etree.ElementTree as ET
import structlog
from datetime import datetime, timedelta

logger = structlog.get_logger()

ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS2 = "http://arxiv.org/schemas/atom"

AI_CATEGORIES = ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.NE", "stat.ML"]


async def search_arxiv(query: str, max_results: int = 10, days_back: int = 14) -> list[dict]:
    """Search arXiv for recent papers matching query."""
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(ARXIV_API, params=params)
            r.raise_for_status()

        root = ET.fromstring(r.text)
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        results = []

        for entry in root.findall(f"{{{ARXIV_NS}}}entry"):
            title_el = entry.find(f"{{{ARXIV_NS}}}title")
            summary_el = entry.find(f"{{{ARXIV_NS}}}summary")
            published_el = entry.find(f"{{{ARXIV_NS}}}published")
            id_el = entry.find(f"{{{ARXIV_NS}}}id")

            if not all([title_el is not None, id_el is not None]):
                continue

            published_str = (published_el.text or "").strip() if published_el is not None else ""
            try:
                published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                if published.replace(tzinfo=None) < cutoff:
                    continue
            except Exception:
                pass

            arxiv_id = (id_el.text or "").strip()
            url = arxiv_id if arxiv_id.startswith("http") else f"https://arxiv.org/abs/{arxiv_id}"

            authors = [
                a.find(f"{{{ARXIV_NS}}}name").text
                for a in entry.findall(f"{{{ARXIV_NS}}}author")
                if a.find(f"{{{ARXIV_NS}}}name") is not None
            ]

            results.append({
                "title": (title_el.text or "").strip().replace("\n", " "),
                "url": url,
                "snippet": (summary_el.text or "").strip()[:300] if summary_el is not None else "",
                "authors": authors[:5],
                "published": published_str,
                "source": "arxiv",
            })

        logger.info("arxiv.search_complete", query=query[:50], results=len(results))
        return results

    except Exception as e:
        logger.warning("arxiv.search_failed", query=query[:50], error=str(e))
        return []


async def get_recent_ai_papers(max_results: int = 10) -> list[dict]:
    """Fetch latest AI/ML papers from arXiv."""
    category_query = " OR ".join(f"cat:{c}" for c in AI_CATEGORIES[:4])
    return await search_arxiv(category_query, max_results=max_results, days_back=7)
