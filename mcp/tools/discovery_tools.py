"""MCP tools for content discovery, extraction, and analysis."""
from fastmcp import FastMCP
import json


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def search_web(query: str, max_results: int = 10) -> str:
        """
        Search the web for content relevant to FRONTIER community topics.
        Uses DuckDuckGo (no API key required).

        Args:
            query: Search query (be specific for best results)
            max_results: Number of results (1-20)
        """
        from backend.services.search_service import search_web as _search
        results = await _search(query, max_results=min(max_results, 20))
        if not results:
            return "No results found."
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet'][:150]}")
        return "\n\n".join(lines)

    @mcp.tool()
    async def search_hackathons(max_results: int = 15) -> str:
        """Search for active and upcoming hackathons. Good for #arena channel."""
        from backend.services.search_service import search_hackathons as _search
        results = await _search(max_results=max_results)
        if not results:
            return "No hackathons found."
        lines = []
        for r in results:
            lines.append(f"• {r['title']}\n  {r['url']}\n  {r['snippet'][:200]}")
        return "\n\n".join(lines)

    @mcp.tool()
    async def search_research(query: str, max_results: int = 10) -> str:
        """
        Search for research papers on arXiv and other academic sources.
        Good for #lab channel content.

        Args:
            query: Research topic (e.g. 'chain of thought reasoning', 'diffusion models')
        """
        from backend.services.search_service import search_research as _search
        results = await _search(query, max_results=max_results)
        if not results:
            return "No research results found."
        lines = []
        for r in results:
            authors = ", ".join(r.get("authors", [])[:3]) or "Unknown"
            published = r.get("published", "")[:10]
            lines.append(
                f"📄 {r['title']}\n"
                f"   Authors: {authors}{(' | ' + published) if published else ''}\n"
                f"   {r['url']}\n"
                f"   {r['snippet'][:200]}"
            )
        return "\n\n".join(lines)

    @mcp.tool()
    async def extract_content(url: str) -> str:
        """
        Fetch and extract clean text from a public URL.
        Use this to get the full content of an article before generating a post.

        Args:
            url: Public HTTPS URL to extract content from
        """
        from backend.services.extraction_service import extract_content as _extract
        result = await _extract(url, max_chars=4000)
        if not result.get("ok"):
            return f"❌ Extraction failed: {result.get('error', 'Unknown error')}"
        return (
            f"✅ Extracted: {result['title']}\n"
            f"Words: {result['word_count']}\n"
            f"URL: {result['canonical_url']}\n\n"
            f"---\n{result['text'][:3000]}"
        )

    @mcp.tool()
    async def analyze_content(url: str) -> str:
        """
        Extract, classify, and score content from a URL for FRONTIER relevance.
        Shows category, relevance scores, and recommended channel before generating.

        Args:
            url: Public URL to analyze
        """
        from backend.services.extraction_service import extract_content as _extract
        from backend.services.relevance_service import (
            classify_content, score_relevance, passes_quality_gate
        )
        from backend.services.style_service import get_channel_for_category

        extracted = await _extract(url, max_chars=3000)
        if not extracted.get("ok"):
            return f"❌ Could not extract: {extracted.get('error')}"

        text = extracted["text"]
        title = extracted["title"]
        scores = score_relevance(text=text, title=title, url=url)
        category = classify_content(text, title)
        channel = get_channel_for_category(category)
        passes = passes_quality_gate(scores)

        score_lines = "\n".join(
            f"  {k}: {v:.0%}" for k, v in scores.items() if k != "overall"
        )
        gate = "✅ PASSES quality gate" if passes else "⚠️  BELOW threshold"

        return (
            f"📊 ANALYSIS: {title[:80]}\n"
            f"{'─' * 50}\n"
            f"Category: {category}\n"
            f"Recommended channel: {channel}\n"
            f"Overall score: {scores['overall']:.0%}\n\n"
            f"Scores:\n{score_lines}\n\n"
            f"{gate}\n\n"
            f"Ready to generate: use generate_post_tool with this URL"
        )

    @mcp.tool()
    async def check_duplicate(title: str, url: str) -> str:
        """
        Check if content has already been posted to FRONTIER.

        Args:
            title: Title of the content
            url: URL of the content
        """
        from backend.database.db import AsyncSessionLocal
        from backend.services.duplicate_service import check_duplicate as _check

        async with AsyncSessionLocal() as db:
            result = await _check(db, url=url, title=title)

        if result["is_duplicate"]:
            return f"⚠️  DUPLICATE: {result['reason']} (matched item: {result['matched_id']})"
        return "✅ Not a duplicate — safe to generate and post."

    @mcp.tool()
    async def score_content(text: str, title: str = "", url: str = "") -> str:
        """
        Score content for FRONTIER relevance without fetching from URL.
        Use when you already have the text.

        Args:
            text: The content text to score
            title: Optional title
            url: Optional source URL (used for credibility scoring)
        """
        from backend.services.relevance_service import score_relevance, classify_content, passes_quality_gate
        from backend.services.style_service import get_channel_for_category

        scores = score_relevance(text=text, title=title, url=url)
        category = classify_content(text, title)
        channel = get_channel_for_category(category)
        passes = passes_quality_gate(scores)

        lines = "\n".join(f"  {k}: {v:.0%}" for k, v in scores.items() if k != "overall")
        return (
            f"Category: {category} → {channel}\n"
            f"Overall: {scores['overall']:.0%}\n"
            f"{'✅ Passes' if passes else '⚠️  Below threshold'}\n\n{lines}"
        )

    @mcp.tool()
    async def discover_content(category: str = "AI", max_items: int = 5) -> str:
        """
        Run a content discovery cycle for a category.
        Searches, extracts, scores, deduplicates, and saves to DB.

        Args:
            category: AI, BUILD, RESEARCH, HACKATHON, OPPORTUNITY, or ALL
            max_items: Max items to save (1-20)
        """
        from backend.database.db import AsyncSessionLocal
        from backend.services import discovery_service

        async with AsyncSessionLocal() as db:
            if category.upper() == "ALL":
                results = await discovery_service.run_full_discovery(db)
                total = sum(results.values())
                breakdown = "\n".join(f"  {k}: {v}" for k, v in results.items())
                return f"✅ Discovery complete: {total} new items\n{breakdown}"
            else:
                items = await discovery_service.discover_by_category(
                    db, category, max_items=min(max_items, 20)
                )
                if not items:
                    return f"No new {category} content found (all duplicates or below threshold)."
                lines = []
                for ci in items:
                    lines.append(
                        f"• [{ci.recommended_channel}] {ci.title[:80]}\n"
                        f"  Score: {ci.overall_relevance:.0%} | {ci.source_url[:60]}"
                    )
                return f"✅ Found {len(items)} new {category} items:\n\n" + "\n\n".join(lines)

    @mcp.tool()
    async def get_discovery_queue(limit: int = 10) -> str:
        """
        Show discovered content waiting to be turned into posts.
        Use draft_from_discovery to generate a post from any item.

        Args:
            limit: Max items to show
        """
        from backend.database.db import AsyncSessionLocal
        from backend.database.models import ContentItem, ContentStatus
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ContentItem)
                .where(ContentItem.status == ContentStatus.ANALYZED)
                .order_by(ContentItem.overall_relevance.desc())
                .limit(limit)
            )
            items = result.scalars().all()

        if not items:
            return "Queue is empty. Run discover_content to find new items."

        lines = []
        for ci in items:
            lines.append(
                f"ID: {ci.id[:8]}...\n"
                f"  Title: {ci.title[:70]}\n"
                f"  Channel: {ci.recommended_channel} | Score: {ci.overall_relevance:.0%}\n"
                f"  URL: {ci.source_url[:60]}"
            )
        return f"📥 Discovery queue ({len(items)} items):\n\n" + "\n\n".join(lines)

    @mcp.tool()
    async def search_x_posts(query: str, max_results: int = 20, days_back: int = 7) -> str:
        """
        Search X (Twitter) for recent public posts.
        Requires X_BEARER_TOKEN in .env. Read-only, no user auth.

        Args:
            query: Search query (X search syntax supported)
            max_results: Max tweets to return (1-100)
            days_back: How far back to search (1-30)
        """
        from backend.services.x_service import search_x
        results = await search_x(query, max_results=min(max_results, 100), days_back=days_back)
        if not results:
            return "No X results. Check X_BEARER_TOKEN is set or adjust query."
        lines = []
        for r in results[:15]:
            likes = r.get("likes", 0)
            rt = r.get("retweets", 0)
            lines.append(
                f"• @{r.get('author', 'unknown')} [{likes}♥ {rt}🔁]\n"
                f"  {r['snippet'][:200]}\n"
                f"  {r['url']}"
            )
        return f"X results for '{query}':\n\n" + "\n\n".join(lines)

    @mcp.tool()
    async def fetch_rss_feeds(category_filter: str = "", max_per_feed: int = 5, days_back: int = 3) -> str:
        """
        Fetch all configured RSS feeds and return recent items.

        Args:
            category_filter: Filter by category (AI, BUILD, RESEARCH, HACKATHON, OPPORTUNITY, or blank for all)
            max_per_feed: Items per feed
            days_back: Only items published within this many days
        """
        from backend.services.rss_service import fetch_all_feeds
        cat = category_filter.upper() if category_filter else None
        items = await fetch_all_feeds(category_filter=cat, max_per_feed=max_per_feed, days_back=days_back)
        if not items:
            return "No RSS items found for given filters."
        lines = []
        for r in items[:20]:
            lines.append(
                f"• [{r.get('category', '?')}] {r['title'][:80]}\n"
                f"  {r['url']}\n"
                f"  {r.get('snippet', '')[:150]}"
            )
        return f"RSS items ({len(items)} total, showing 20):\n\n" + "\n\n".join(lines)

    @mcp.tool()
    async def fetch_hackathons(max_items: int = 20) -> str:
        """
        Fetch hackathons from Devpost and MLH.
        Returns structured list of upcoming hackathons with registration links.

        Args:
            max_items: Max hackathons to return
        """
        from backend.services.hackathon_service import discover_hackathons
        items = await discover_hackathons(max_items=min(max_items, 50))
        if not items:
            return "No hackathons found. Try search_hackathons as fallback."
        lines = []
        for h in items:
            deadline = h.get("deadline", "")
            prize = h.get("prize_pool", "")
            lines.append(
                f"• {h['title']}\n"
                f"  {h['url']}\n"
                + (f"  Deadline: {deadline}\n" if deadline else "")
                + (f"  Prize: {prize}\n" if prize else "")
                + f"  {h.get('snippet', '')[:150]}"
            )
        return f"Hackathons ({len(items)}):\n\n" + "\n\n".join(lines)

    @mcp.tool()
    async def run_scheduled_job(job_id: str) -> str:
        """
        Manually trigger one of FRONTIER's scheduled discovery jobs.

        Args:
            job_id: One of: discover_ai, fetch_rss, discover_research,
                    discover_hackathons, fetch_x, discover_opportunities
        """
        from backend.services.scheduler_service import DEFAULT_JOBS
        valid = {cfg["id"]: cfg for cfg in DEFAULT_JOBS}
        if job_id not in valid:
            return f"Unknown job '{job_id}'. Valid: {', '.join(valid)}"
        cfg = valid[job_id]
        await cfg["func"]()
        return f"✅ Job '{job_id}' ({cfg['description']}) completed."
