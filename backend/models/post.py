from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime


VALID_CHANNELS = [
    "#signal", "#frontier-guide", "#frontier-lounge",
    "#forge", "#bug-hunt", "#neural", "#lab",
    "#arena", "#missions", "#launchpad",
]

VALID_CATEGORIES = ["AI", "BUILD", "RESEARCH", "HACKATHON", "PITCHING", "DEBUGGING", "OPPORTUNITY", "GENERAL"]


class GeneratePostRequest(BaseModel):
    topic: str = Field(..., min_length=10, max_length=4000, description="Topic or content to generate a post about")
    channel: str | None = Field(None, description="Target Discord channel (auto-routed if omitted)")
    category: str = Field("GENERAL", description="Content category")
    source_url: str | None = Field(None, description="Source URL for the content")
    extra_context: str | None = Field(None, max_length=2000)


class GeneratePostResponse(BaseModel):
    id: str
    content: str
    channel: str
    category: str
    source_url: str | None
    content_hash: str
    model: str
    provider: str
    status: str = "DRAFTED"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PreviewPost(BaseModel):
    id: str
    content: str
    channel: str
    category: str
    source_url: str | None
    status: str
    created_at: datetime


class PublishRequest(BaseModel):
    post_id: str


class PublishResponse(BaseModel):
    post_id: str
    discord_message_id: str
    channel: str
    published_at: datetime


class RegenerateRequest(BaseModel):
    post_id: str
    feedback: str = Field(..., min_length=5, max_length=1000)


class ApproveRequest(BaseModel):
    post_id: str


class RejectRequest(BaseModel):
    post_id: str | None = None  # optional — taken from URL path
    reason: str | None = None
