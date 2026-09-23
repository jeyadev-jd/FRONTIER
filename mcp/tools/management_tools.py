"""MCP tools for system management, style, and health."""
from fastmcp import FastMCP
from backend.services.llm.factory import get_llm_provider
from pathlib import Path

STYLE_DIR = Path(__file__).parent.parent.parent / "style_examples"


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def get_style_profile() -> str:
        """Get the current FRONTIER style profile — tone, formality, vocabulary, etc."""
        try:
            from backend.database.db import AsyncSessionLocal
            from backend.services.style_profile_service import get_active_profile
            async with AsyncSessionLocal() as db:
                profile = await get_active_profile(db)
            if not profile:
                return (
                    "No style profile built yet.\n"
                    "Add writing examples with add_style_example, then call rebuild_style_profile."
                )
            attrs = profile.full_attributes or {}
            import json
            return (
                f"FRONTIER Style Profile: {profile.name}\n"
                f"Examples used: {profile.example_count}\n"
                f"Last updated: {profile.updated_at}\n\n"
                f"Attributes:\n{json.dumps(attrs, indent=2)}"
            )
        except Exception as e:
            return f"Error loading profile: {e}"

    @mcp.tool()
    async def add_style_example(
        content: str,
        category: str = "general",
        source_label: str | None = None,
    ) -> str:
        """
        Add a writing style example to the profile library.
        The admin's own writing should be pasted here — NOT automatically scraped.

        Args:
            content: Example text showing the desired writing style (min 50 chars)
            category: ai | research | hackathons | announcements | general | build | debugging
            source_label: Optional label (e.g. 'my #neural post from Jan 2025')
        """
        if len(content) < 50:
            return "ERROR: Example must be at least 50 characters."

        valid = ["ai", "research", "hackathons", "announcements", "general", "build", "debugging"]
        if category not in valid:
            return f"ERROR: category must be one of {valid}"

        try:
            from backend.database.db import AsyncSessionLocal
            from backend.database.models import StyleExample
            async with AsyncSessionLocal() as db:
                ex = StyleExample(category=category, content=content, source_label=source_label)
                db.add(ex)
                await db.commit()
                ex_id = ex.id
            return (
                f"✅ Style example saved (id: {ex_id[:8]})\n"
                f"Category: {category}\n"
                f"Preview: {content[:80]}...\n\n"
                f"Call rebuild_style_profile to update the active profile."
            )
        except Exception as e:
            return f"ERROR saving example: {e}"

    @mcp.tool()
    async def rebuild_style_profile() -> str:
        """
        Re-analyze all style examples and rebuild the active style profile.
        Run this after adding new examples.
        Takes ~10-30 seconds depending on LLM speed.
        """
        try:
            from backend.database.db import AsyncSessionLocal
            from backend.services.style_profile_service import rebuild_profile
            async with AsyncSessionLocal() as db:
                profile = await rebuild_profile(db)
            return (
                f"✅ Style profile rebuilt: {profile.name}\n"
                f"Examples analyzed: {profile.example_count}\n"
                f"Tone: {profile.tone}\n"
                f"Formality: {profile.formality}\n"
                f"Technical depth: {profile.technical_depth}\n"
                f"Emoji usage: {profile.emoji_usage}\n\n"
                f"Profile is now active. Future generated posts will use this style."
            )
        except Exception as e:
            return f"ERROR rebuilding profile: {e}"

    @mcp.tool()
    async def preview_style_injection(channel: str = "#neural") -> str:
        """
        Preview the exact style instructions that will be injected into generation prompts.
        Use to verify the style profile is working as expected.

        Args:
            channel: Target channel (affects style context)
        """
        try:
            from backend.database.db import AsyncSessionLocal
            from backend.services.style_profile_service import get_style_injection_for_generation
            async with AsyncSessionLocal() as db:
                injection = await get_style_injection_for_generation(db, channel)
            if not injection:
                return "No style injection active (no profile built yet)."
            return f"Style injection for {channel}:\n{'─' * 40}\n{injection}"
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    async def analyze_writing_sample(text: str) -> str:
        """
        Analyze a piece of writing to extract its style characteristics.
        Use this to preview what style profile would be extracted from a sample.
        Does NOT save anything.

        Args:
            text: Writing sample to analyze (min 100 chars recommended)
        """
        from backend.services.style_profile_service import analyze_style_examples, build_style_injection
        import json
        attrs = await analyze_style_examples([text])
        injection = build_style_injection(attrs)
        return (
            f"Style Analysis:\n{'─' * 40}\n"
            f"{json.dumps(attrs, indent=2)}\n\n"
            f"Injection preview:\n{'─' * 40}\n{injection}"
        )

    @mcp.tool()
    async def list_style_examples(category: str | None = None) -> str:
        """
        List stored style examples.

        Args:
            category: Filter by category (optional)
        """
        try:
            from backend.database.db import AsyncSessionLocal
            from backend.database.models import StyleExample
            from sqlalchemy import select
            async with AsyncSessionLocal() as db:
                q = select(StyleExample).order_by(StyleExample.created_at.desc()).limit(20)
                if category:
                    q = q.where(StyleExample.category == category)
                result = await db.execute(q)
                examples = result.scalars().all()

            if not examples:
                return "No style examples stored yet."

            lines = []
            for ex in examples:
                label = f" [{ex.source_label}]" if ex.source_label else ""
                lines.append(
                    f"• [{ex.category}]{label} id:{ex.id[:8]}\n"
                    f"  {ex.content[:100]}..."
                )
            return f"Style examples ({len(examples)}):\n\n" + "\n\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    async def check_llm_status() -> str:
        """Check if the local LLM is available and list available models."""
        llm = get_llm_provider()
        ok = await llm.health_check()
        models = await llm.list_models()
        status = "✅ Online" if ok else "❌ Offline"
        return (
            f"LLM: {status}\n"
            f"Provider: {llm.provider_name}\n"
            f"Models: {', '.join(models) if models else 'none detected'}"
        )

    @mcp.tool()
    async def get_recent_posts(limit: int = 10) -> str:
        """Get recently published posts."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"http://localhost:8000/posts/published?limit={limit}")
                if r.status_code == 200:
                    posts = r.json()
                    if not posts:
                        return "No published posts yet."
                    lines = [
                        f"[{p['channel']}] {p['content'][:100]}..."
                        for p in posts[:limit]
                    ]
                    return "\n\n".join(lines)
                return f"API returned {r.status_code}"
        except Exception as e:
            return f"Could not fetch posts (is backend running?): {e}"

    @mcp.tool()
    async def get_approval_queue(limit: int = 10) -> str:
        """
        Show posts awaiting human approval.
        Use approve_post or reject_post to act on them.

        Args:
            limit: Max posts to show
        """
        from backend.database.db import AsyncSessionLocal
        from backend.services.queue_service import get_pending_queue

        async with AsyncSessionLocal() as db:
            posts = await get_pending_queue(db, limit=limit)

        if not posts:
            return "Approval queue is empty. Run queue_cycle to auto-draft new items."

        lines = []
        for p in posts:
            lines.append(
                f"ID: {p.id[:8]}  |  Channel: {p.channel}\n"
                f"  {p.generated_content[:200]}{'…' if len(p.generated_content) > 200 else ''}"
            )
        return f"Pending approval ({len(posts)}):\n\n" + "\n\n".join(lines)

    @mcp.tool()
    async def run_queue_cycle() -> str:
        """
        Run the auto-draft + expiry queue cycle manually.
        Drafts high-relevance discovered items and expires stale content.
        """
        from backend.services.queue_service import run_queue_cycle as _cycle
        result = await _cycle()
        return (
            f"Queue cycle complete:\n"
            f"  Auto-drafted: {result['drafted']} posts\n"
            f"  Expired: {result['expired']} items\n"
            f"  Discord notified: {result['notified']}"
        )

    @mcp.tool()
    async def get_analytics_summary(days: int = 7) -> str:
        """
        Show FRONTIER analytics: discovery funnel, publish rate, top channels.

        Args:
            days: Lookback window in days (1-90)
        """
        from backend.database.db import AsyncSessionLocal
        from backend.services.analytics_service import get_funnel_stats, get_channel_breakdown, get_category_breakdown

        async with AsyncSessionLocal() as db:
            funnel = await get_funnel_stats(db, days=days)
            channels = await get_channel_breakdown(db, days=days)
            categories = await get_category_breakdown(db, days=days)

        ch_lines = "\n".join(f"  {r['channel']}: {r['count']}" for r in channels[:6])
        cat_lines = "\n".join(f"  {r['category']}: {r['count']}" for r in categories[:6])

        return (
            f"FRONTIER Analytics — last {days} days\n"
            f"{'─' * 40}\n"
            f"Discovered:        {funnel['discovered']}\n"
            f"Analyzed:          {funnel['analyzed']}\n"
            f"Drafted:           {funnel['drafted']}\n"
            f"Pending approval:  {funnel['pending_approval']}\n"
            f"Published:         {funnel['published']}\n"
            f"Rejected:          {funnel['rejected']}\n"
            f"Expired:           {funnel['expired']}\n"
            f"Dupes blocked:     {funnel['duplicates_blocked']}\n"
            f"Publish rate:      {funnel['publish_rate']:.0%}\n"
            f"Duplicate rate:    {funnel['duplicate_rate']:.0%}\n"
            f"\nTop channels:\n{ch_lines or '  (none yet)'}\n"
            f"\nTop categories:\n{cat_lines or '  (none yet)'}"
        )
