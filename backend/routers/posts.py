"""Post management API routes."""
import uuid
import base64
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from backend.database.db import get_db
from backend.database.models import Post, ContentItem, ContentStatus, ContentCategory
from backend.models.post import (
    GeneratePostRequest, GeneratePostResponse,
    RegenerateRequest, ApproveRequest, RejectRequest,
    PublishRequest, PublishResponse, PreviewPost,
)
from backend.services.generation_service import generate_post, regenerate_post
from backend.services import discord_service

logger = structlog.get_logger()
router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("/generate", response_model=GeneratePostResponse)
async def api_generate_post(
    req: GeneratePostRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await generate_post(
        topic=req.topic,
        channel=req.channel,
        category=req.category,
        source_url=req.source_url,
        extra_context=req.extra_context,
        db=db,
    )

    post_id = str(uuid.uuid4())

    post = Post(
        id=post_id,
        channel=result["channel"],
        generated_content=result["content"],
        status=ContentStatus.DRAFTED,
    )
    db.add(post)
    await db.commit()

    return GeneratePostResponse(
        id=post_id,
        content=result["content"],
        channel=result["channel"],
        category=result["category"],
        source_url=result["source_url"],
        content_hash=result["content_hash"],
        model=result["model"],
        provider=result["provider"],
    )


@router.post("/generate-with-file", response_model=GeneratePostResponse)
async def api_generate_post_with_file(
    topic: str = Form(...),
    channel: str = Form(""),
    category: str = Form("GENERAL"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Generate a post with an attached file (image, video, document) as extra context."""
    content_type = file.content_type or ""
    file_bytes = await file.read()
    file_size_kb = len(file_bytes) / 1024

    extra_context = f"Attached file: {file.filename} ({content_type}, {file_size_kb:.0f} KB)"

    # For images, describe what was attached so LLM knows context
    if content_type.startswith("image/"):
        extra_context = (
            f"The user attached an image: {file.filename}. "
            f"Use the topic/caption they provided to generate the post. "
            f"The image will be posted to Discord alongside the text."
        )
    elif content_type.startswith("video/"):
        extra_context = (
            f"The user attached a video: {file.filename}. "
            f"Use the topic/caption they provided to generate the post. "
            f"The video will be posted to Discord alongside the text."
        )
    elif content_type in ("application/pdf",):
        extra_context = f"The user attached a PDF document: {file.filename}. Generate a post based on the topic they described."
    elif content_type.startswith("text/") or file.filename.endswith((".md", ".txt", ".csv")):
        # Read text content as extra context
        try:
            text_content = file_bytes.decode("utf-8", errors="ignore")[:2000]
            extra_context = f"Attached text file content:\n{text_content}"
        except Exception:
            pass

    result = await generate_post(
        topic=topic,
        channel=channel or None,
        category=category,
        extra_context=extra_context,
        db=db,
    )

    post_id = str(uuid.uuid4())
    post = Post(
        id=post_id,
        channel=result["channel"],
        generated_content=result["content"],
        status=ContentStatus.DRAFTED,
    )
    db.add(post)
    await db.commit()

    return GeneratePostResponse(
        id=post_id,
        content=result["content"],
        channel=result["channel"],
        category=result["category"],
        source_url=result["source_url"],
        content_hash=result["content_hash"],
        model=result["model"],
        provider=result["provider"],
    )


@router.post("/regenerate", response_model=GeneratePostResponse)
async def api_regenerate_post(
    req: RegenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    post = await db.get(Post, req.post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    result = await regenerate_post(
        original_content=post.generated_content,
        feedback=req.feedback,
        channel=post.channel,
        db=db,
    )

    post.generated_content = result["content"]
    post.status = ContentStatus.DRAFTED
    await db.commit()

    return GeneratePostResponse(
        id=post.id,
        content=result["content"],
        channel=result["channel"],
        category=result.get("category", "GENERAL"),
        source_url=None,
        content_hash=result["content_hash"],
        model=result["model"],
        provider=result["provider"],
    )


@router.post("/{post_id}/approve")
async def api_approve_post(
    post_id: str,
    db: AsyncSession = Depends(get_db),
):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    post.status = ContentStatus.APPROVED
    await db.commit()
    return {"status": "approved", "post_id": post_id}


@router.post("/{post_id}/approve-and-publish", response_model=PublishResponse)
async def api_approve_and_publish(
    post_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Approve and publish in one atomic step — used by Publish button."""
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status == ContentStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="Post already published")

    post.status = ContentStatus.APPROVED
    await db.commit()

    try:
        msg = await discord_service.send_message(post.channel, post.generated_content)
        post.status = ContentStatus.PUBLISHED
        post.discord_message_id = msg.get("id")
        post.published_at = datetime.utcnow()
        await db.commit()

        return PublishResponse(
            post_id=post.id,
            discord_message_id=msg.get("id", ""),
            channel=post.channel,
            published_at=post.published_at,
        )
    except Exception as e:
        post.status = ContentStatus.FAILED
        post.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=502, detail=f"Discord publish failed: {e}")


@router.post("/{post_id}/reject")
async def api_reject_post(
    post_id: str,
    db: AsyncSession = Depends(get_db),
    reason: str | None = None,
):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    post.status = ContentStatus.REJECTED
    post.error_message = reason
    await db.commit()
    return {"status": "rejected", "post_id": post_id}


@router.post("/{post_id}/publish", response_model=PublishResponse)
async def api_publish_post(
    post_id: str,
    db: AsyncSession = Depends(get_db),
):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status not in (ContentStatus.APPROVED, ContentStatus.DRAFTED):
        raise HTTPException(status_code=400, detail=f"Post status is {post.status}, cannot publish")

    try:
        msg = await discord_service.send_message(post.channel, post.generated_content)
        post.status = ContentStatus.PUBLISHED
        post.discord_message_id = msg.get("id")
        post.published_at = datetime.utcnow()
        await db.commit()

        return PublishResponse(
            post_id=post.id,
            discord_message_id=msg.get("id", ""),
            channel=post.channel,
            published_at=post.published_at,
        )
    except Exception as e:
        post.status = ContentStatus.FAILED
        post.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=502, detail=f"Discord publish failed: {e}")


@router.get("/pending", response_model=list[PreviewPost])
async def api_list_pending(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Post).where(
            Post.status.in_([ContentStatus.DRAFTED, ContentStatus.PENDING_APPROVAL, ContentStatus.APPROVED])
        ).order_by(Post.created_at.desc()).limit(50)
    )
    posts = result.scalars().all()
    return [
        PreviewPost(
            id=p.id,
            content=p.generated_content,
            channel=p.channel,
            category="GENERAL",
            source_url=None,
            status=p.status.value,
            created_at=p.created_at,
        )
        for p in posts
    ]


@router.get("/published", response_model=list[PreviewPost])
async def api_list_published(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Post).where(Post.status == ContentStatus.PUBLISHED)
        .order_by(Post.published_at.desc()).limit(50)
    )
    posts = result.scalars().all()
    return [
        PreviewPost(
            id=p.id,
            content=p.generated_content,
            channel=p.channel,
            category="GENERAL",
            source_url=None,
            status=p.status.value,
            created_at=p.published_at or p.created_at,
        )
        for p in posts
    ]
