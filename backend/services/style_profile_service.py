"""
Style Profile Service — Phase 3.

Ingests the admin's writing examples, uses local LLM to extract style attributes,
stores a profile, and injects it into generation prompts.

Priority order (NEVER override higher tiers):
  FACTUAL ACCURACY > COMMUNITY RULES > CHANNEL FORMAT > FRONTIER STYLE > PERSONAL STYLE
"""
import json
import structlog
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database.models import StyleProfile, StyleExample
from backend.services.llm.factory import get_llm_provider

logger = structlog.get_logger()

STYLE_DIR = Path(__file__).parent.parent.parent / "style_examples"

ANALYSIS_SYSTEM = """You are a writing style analyst.
Analyze the provided writing samples and extract precise style characteristics.
Be specific and factual — describe what IS in the writing, not what you wish were there.
Output only valid JSON."""

ANALYSIS_PROMPT = """Analyze these writing samples from the same author.
Extract their writing style as a JSON object with these exact keys:

{
  "tone": ["list", "of", "adjectives"],
  "sentence_length": "short|medium|long|mixed",
  "technical_depth": "beginner|intermediate|advanced|varies",
  "humor_level": "none|subtle|moderate|high",
  "emoji_usage": "none|minimal|moderate|heavy",
  "formality": "casual|conversational|semi-formal|formal",
  "vocabulary": {
    "preferred": ["words/phrases they use often"],
    "avoided": ["words/phrases they never use"]
  },
  "structural_patterns": ["how they structure posts, e.g. 'opens with question', 'uses bold headers'"],
  "preferred_expressions": ["signature phrases or openers"],
  "things_to_avoid": ["what NOT to do when imitating this style"],
  "opening_style": "how they typically open a post",
  "closing_style": "how they typically close a post",
  "punctuation_style": "how they use punctuation distinctively",
  "summary": "one sentence describing the overall voice"
}

Writing samples:
---
{samples}
---

Output ONLY the JSON object. No explanation."""


async def analyze_style_examples(examples: list[str]) -> dict:
    """Use local LLM to analyze writing examples and extract style attributes."""
    if not examples:
        return _default_profile_attributes()

    # Limit to first 5 examples, cap total length
    selected = examples[:5]
    joined = "\n\n---\n\n".join(s[:600] for s in selected)
    total = joined[:4000]

    llm = get_llm_provider()
    prompt = ANALYSIS_PROMPT.replace("{samples}", total)

    logger.info("style.analyzing", examples=len(selected))
    response = await llm.generate(prompt=prompt, system=ANALYSIS_SYSTEM, temperature=0.3)

    raw = response.content.strip()

    # Extract JSON if wrapped in markdown
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    try:
        attributes = json.loads(raw)
        logger.info("style.analysis_complete")
        return attributes
    except json.JSONDecodeError as e:
        logger.warning("style.json_parse_failed", error=str(e), raw=raw[:200])
        return _default_profile_attributes()


def _default_profile_attributes() -> dict:
    return {
        "tone": ["energetic", "technical", "clear", "conversational"],
        "sentence_length": "medium",
        "technical_depth": "intermediate",
        "humor_level": "subtle",
        "emoji_usage": "moderate",
        "formality": "conversational",
        "vocabulary": {
            "preferred": ["build", "ship", "try", "learn", "practical"],
            "avoided": ["synergy", "leverage", "utilize", "paradigm shift"],
        },
        "structural_patterns": ["opens with bold claim", "uses headers", "ends with action item"],
        "preferred_expressions": [],
        "things_to_avoid": ["corporate speak", "excessive hype", "vague claims"],
        "opening_style": "direct question or bold statement",
        "closing_style": "actionable next step",
        "punctuation_style": "minimal, clean",
        "summary": "Energetic and technically precise, focused on student practicality.",
    }


def build_style_injection(attributes: dict, channel: str = "") -> str:
    """
    Build a style instruction block to inject into generation prompts.
    This goes AFTER channel format instructions (lower priority).
    """
    if not attributes:
        return ""

    lines = ["WRITING STYLE GUIDE (apply after channel format):"]

    summary = attributes.get("summary")
    if summary:
        lines.append(f"Voice: {summary}")

    tone = attributes.get("tone", [])
    if tone:
        lines.append(f"Tone: {', '.join(tone[:5])}")

    formality = attributes.get("formality")
    if formality:
        lines.append(f"Formality: {formality}")

    sentence_len = attributes.get("sentence_length")
    if sentence_len:
        lines.append(f"Sentence length: {sentence_len}")

    emoji = attributes.get("emoji_usage")
    if emoji:
        lines.append(f"Emoji usage: {emoji}")

    tech_depth = attributes.get("technical_depth")
    if tech_depth:
        lines.append(f"Technical depth: {tech_depth}")

    vocab = attributes.get("vocabulary", {})
    preferred = vocab.get("preferred", [])
    avoided = vocab.get("avoided", [])
    if preferred:
        lines.append(f"Use words like: {', '.join(preferred[:6])}")
    if avoided:
        lines.append(f"Never use: {', '.join(avoided[:6])}")

    patterns = attributes.get("structural_patterns", [])
    if patterns:
        lines.append(f"Structure: {'; '.join(patterns[:3])}")

    expressions = attributes.get("preferred_expressions", [])
    if expressions:
        lines.append(f"Signature phrases: {'; '.join(expressions[:3])}")

    avoid = attributes.get("things_to_avoid", [])
    if avoid:
        lines.append(f"Avoid: {'; '.join(avoid[:4])}")

    opening = attributes.get("opening_style")
    if opening:
        lines.append(f"Opening style: {opening}")

    closing = attributes.get("closing_style")
    if closing:
        lines.append(f"Closing style: {closing}")

    return "\n".join(lines)


async def get_active_profile(db: AsyncSession) -> StyleProfile | None:
    result = await db.execute(
        select(StyleProfile).where(StyleProfile.is_active == True).limit(1)
    )
    return result.scalar_one_or_none()


async def load_style_examples_from_db(db: AsyncSession, category: str | None = None) -> list[str]:
    """Load style examples from DB, optionally filtered by category."""
    query = select(StyleExample)
    if category:
        query = query.where(StyleExample.category == category)
    query = query.order_by(StyleExample.created_at.desc()).limit(10)
    result = await db.execute(query)
    examples = result.scalars().all()
    return [ex.content for ex in examples]


async def load_style_examples_from_files(category: str | None = None) -> list[str]:
    """Load style examples from the style_examples/ directory."""
    if category:
        dirs = [STYLE_DIR / category]
    else:
        dirs = [d for d in STYLE_DIR.iterdir() if d.is_dir()] if STYLE_DIR.exists() else []

    examples = []
    for d in dirs:
        for f in sorted(d.glob("*.txt"))[:3]:
            try:
                text = f.read_text(encoding="utf-8").strip()
                if text:
                    examples.append(text)
            except Exception:
                pass
    return examples


async def rebuild_profile(db: AsyncSession, profile_name: str = "default") -> StyleProfile:
    """
    Re-analyze all style examples and rebuild the active profile.
    Creates profile if it doesn't exist.
    """
    # Load examples from both DB and files
    db_examples = await load_style_examples_from_db(db)
    file_examples = await load_style_examples_from_files()
    all_examples = db_examples + file_examples

    if not all_examples:
        logger.warning("style.no_examples", msg="Using default profile attributes")
        attributes = _default_profile_attributes()
    else:
        attributes = await analyze_style_examples(all_examples)

    # Upsert profile
    result = await db.execute(
        select(StyleProfile).where(StyleProfile.name == profile_name).limit(1)
    )
    profile = result.scalar_one_or_none()

    if profile is None:
        profile = StyleProfile(name=profile_name)
        db.add(profile)

    # Map analyzed attributes to model fields
    profile.tone = ", ".join(attributes.get("tone", []))
    profile.sentence_length = attributes.get("sentence_length", "medium")
    profile.technical_depth = attributes.get("technical_depth", "intermediate")
    profile.humor_level = attributes.get("humor_level", "subtle")
    profile.emoji_usage = attributes.get("emoji_usage", "moderate")
    profile.formality = attributes.get("formality", "conversational")
    profile.vocabulary = attributes.get("vocabulary", {})
    profile.structure = attributes.get("structural_patterns", [])
    profile.preferred_expressions = attributes.get("preferred_expressions", [])
    profile.things_to_avoid = attributes.get("things_to_avoid", [])
    profile.full_attributes = attributes
    profile.example_count = len(all_examples)
    profile.is_active = True

    await db.commit()
    await db.refresh(profile)

    logger.info("style.profile_rebuilt", name=profile_name, examples=len(all_examples))
    return profile


async def get_style_injection_for_generation(db: AsyncSession, channel: str = "") -> str:
    """Get the style injection string to append to generation prompts."""
    profile = await get_active_profile(db)
    if profile is None:
        # Fall back to file-based examples
        file_examples = await load_style_examples_from_files()
        if not file_examples:
            return ""
        attributes = await analyze_style_examples(file_examples)
        return "\n\n" + build_style_injection(attributes, channel)

    attrs = profile.full_attributes or {}
    if not attrs:
        # Reconstruct from individual fields
        attrs = {
            "tone": profile.tone.split(", ") if profile.tone else [],
            "sentence_length": profile.sentence_length,
            "technical_depth": profile.technical_depth,
            "humor_level": profile.humor_level,
            "emoji_usage": profile.emoji_usage,
            "formality": profile.formality,
            "vocabulary": profile.vocabulary or {},
            "structural_patterns": profile.structure or [],
            "preferred_expressions": profile.preferred_expressions or [],
            "things_to_avoid": profile.things_to_avoid or [],
        }

    injection = build_style_injection(attrs, channel)
    return f"\n\n{injection}" if injection else ""
