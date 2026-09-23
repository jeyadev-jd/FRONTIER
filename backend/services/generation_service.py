"""Core content generation service using local LLM + style profile."""
import hashlib
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.llm.factory import get_llm_provider
from backend.services.style_service import (
    FRONTIER_SYSTEM_PROMPT,
    load_style_examples,
    get_channel_for_category,
    get_channel_template,
)

logger = structlog.get_logger()


async def generate_post(
    topic: str,
    channel: str | None = None,
    category: str = "GENERAL",
    source_url: str | None = None,
    extra_context: str | None = None,
    db: AsyncSession | None = None,
) -> dict:
    """Generate a FRONTIER-style Discord post. Returns dict with content, channel, etc."""
    llm = get_llm_provider()

    if channel is None:
        channel = get_channel_for_category(category)

    template_hint = get_channel_template(channel)

    # Build style injection — Phase 3: use DB profile if available, else file examples
    style_injection = ""
    if db is not None:
        try:
            from backend.services.style_profile_service import get_style_injection_for_generation
            style_injection = await get_style_injection_for_generation(db, channel)
        except Exception as e:
            logger.warning("generation.style_profile_error", error=str(e))
            style_injection = _file_style_fallback(category)
    else:
        style_injection = _file_style_fallback(category)

    source_line = f"\n\nSource URL: {source_url}" if source_url else ""
    extra_line = f"\n\nAdditional context: {extra_context}" if extra_context else ""

    prompt = (
        f"Generate a FRONTIER Discord post for channel {channel}.\n\n"
        f"Topic/Content: {topic}{source_line}{extra_line}\n\n"
        "Channel format template (follow this structure):\n"
        f"{template_hint}\n\n"
        "Fill in all placeholder fields with real, accurate content.\n"
        "Do NOT invent facts. If you do not know something, omit that field.\n"
        f"Keep it student-focused, practical, and energetic.{style_injection}\n\n"
        "Output ONLY the final Discord message, ready to paste. No explanations."
    )

    logger.info("generation.start", channel=channel, category=category)
    response = await llm.generate(prompt=prompt, system=FRONTIER_SYSTEM_PROMPT)
    content = response.content.strip()
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    logger.info("generation.complete", channel=channel, tokens=response.completion_tokens)

    return {
        "content": content,
        "channel": channel,
        "category": category,
        "source_url": source_url,
        "content_hash": content_hash,
        "model": response.model,
        "provider": llm.provider_name,
    }


async def regenerate_post(
    original_content: str,
    feedback: str,
    channel: str,
    category: str = "GENERAL",
    db: AsyncSession | None = None,
) -> dict:
    """Regenerate a post with admin feedback."""
    llm = get_llm_provider()

    style_injection = ""
    if db is not None:
        try:
            from backend.services.style_profile_service import get_style_injection_for_generation
            style_injection = await get_style_injection_for_generation(db, channel)
        except Exception:
            style_injection = _file_style_fallback(category)
    else:
        style_injection = _file_style_fallback(category)

    prompt = (
        f"You wrote this Discord post for FRONTIER channel {channel}:\n\n"
        f"---\n{original_content}\n---\n\n"
        f"The admin gave this feedback: {feedback}\n\n"
        "Rewrite the post addressing the feedback while keeping FRONTIER style.\n"
        f"Output ONLY the rewritten Discord message. No explanations.{style_injection}"
    )

    response = await llm.generate(prompt=prompt, system=FRONTIER_SYSTEM_PROMPT)
    content = response.content.strip()
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

    return {
        "content": content,
        "channel": channel,
        "category": category,
        "content_hash": content_hash,
        "model": response.model,
        "provider": llm.provider_name,
    }


def _file_style_fallback(category: str) -> str:
    """Load style examples from files as fallback when no DB session."""
    examples = load_style_examples(category.lower())
    return examples if examples else ""
