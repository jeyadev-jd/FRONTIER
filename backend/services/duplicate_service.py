"""Duplicate detection — exact (hash) and near-duplicate (title similarity)."""
import hashlib
import re
import structlog
from difflib import SequenceMatcher
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = structlog.get_logger()


def _normalize_url(url: str) -> str:
    """Strip tracking params and fragments for canonical comparison."""
    import re
    url = re.sub(r"[?&](utm_[^&]+|fbclid=[^&]+|ref=[^&]+)", "", url)
    url = re.sub(r"#.*$", "", url)
    url = url.rstrip("/")
    return url.lower()


def _title_hash(title: str) -> str:
    """Hash a normalized title for quick exact-duplicate detection."""
    normalized = re.sub(r"[^\w\s]", "", title.lower().strip())
    normalized = re.sub(r"\s+", " ", normalized)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _content_hash(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(cleaned.encode()).hexdigest()[:24]


def _title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


async def check_duplicate(
    db: AsyncSession,
    url: str,
    title: str,
    content_hash: str | None = None,
    similarity_threshold: float = 0.85,
) -> dict:
    """
    Check if content is a duplicate of anything already in the DB.

    Returns: {is_duplicate: bool, reason: str, matched_id: str|None}
    """
    from backend.database.models import ContentItem

    canonical = _normalize_url(url)
    t_hash = _title_hash(title)

    # 1. Exact URL match
    result = await db.execute(
        select(ContentItem).where(ContentItem.canonical_url == canonical).limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return {"is_duplicate": True, "reason": "exact_url", "matched_id": existing.id}

    # 2. Title hash match
    result = await db.execute(
        select(ContentItem).where(ContentItem.title_hash == t_hash).limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return {"is_duplicate": True, "reason": "exact_title", "matched_id": existing.id}

    # 3. Content hash match
    if content_hash:
        result = await db.execute(
            select(ContentItem).where(ContentItem.content_hash == content_hash).limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return {"is_duplicate": True, "reason": "exact_content", "matched_id": existing.id}

    # 4. Near-duplicate title check (recent items only)
    result = await db.execute(
        select(ContentItem).order_by(ContentItem.created_at.desc()).limit(200)
    )
    recent = result.scalars().all()
    for item in recent:
        if item.title and _title_similarity(title, item.title) >= similarity_threshold:
            return {
                "is_duplicate": True,
                "reason": f"similar_title ({_title_similarity(title, item.title):.0%})",
                "matched_id": item.id,
            }

    return {"is_duplicate": False, "reason": None, "matched_id": None}


def compute_hashes(title: str, text: str, url: str) -> dict:
    return {
        "canonical_url": _normalize_url(url),
        "title_hash": _title_hash(title),
        "content_hash": _content_hash(text),
    }
