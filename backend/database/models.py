from sqlalchemy import (
    Column, String, Float, Boolean, DateTime, Text, Integer,
    ForeignKey, Enum as SAEnum, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database.db import Base
import enum
import uuid


def new_uuid() -> str:
    return str(uuid.uuid4())


class ContentStatus(str, enum.Enum):
    DISCOVERED = "DISCOVERED"
    ANALYZED = "ANALYZED"
    DRAFTED = "DRAFTED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class ContentCategory(str, enum.Enum):
    AI = "AI"
    BUILD = "BUILD"
    RESEARCH = "RESEARCH"
    HACKATHON = "HACKATHON"
    PITCHING = "PITCHING"
    DEBUGGING = "DEBUGGING"
    OPPORTUNITY = "OPPORTUNITY"
    GENERAL = "GENERAL"
    IGNORE = "IGNORE"


class SourceType(str, enum.Enum):
    RSS = "RSS"
    WEB_SEARCH = "WEB_SEARCH"
    ARXIV = "ARXIV"
    X = "X"
    MANUAL = "MANUAL"
    DEVPOST = "DEVPOST"
    MLH = "MLH"


class ContentItem(Base):
    __tablename__ = "content_items"

    id = Column(String, primary_key=True, default=new_uuid)
    source_url = Column(String, nullable=True)
    canonical_url = Column(String, nullable=True)
    title = Column(String, nullable=True)
    raw_content = Column(Text, nullable=True)
    content_hash = Column(String, nullable=True, index=True)
    title_hash = Column(String, nullable=True, index=True)
    category = Column(SAEnum(ContentCategory), nullable=True)
    status = Column(SAEnum(ContentStatus), default=ContentStatus.DISCOVERED, nullable=False)
    relevance_scores = Column(JSON, nullable=True)
    overall_relevance = Column(Float, nullable=True)
    credibility_score = Column(Float, nullable=True)
    recommended_channel = Column(String, nullable=True)
    source_type = Column(SAEnum(SourceType), default=SourceType.WEB_SEARCH, nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    posts = relationship("Post", back_populates="content_item")


class Post(Base):
    __tablename__ = "posts"

    id = Column(String, primary_key=True, default=new_uuid)
    content_item_id = Column(String, ForeignKey("content_items.id"), nullable=True)
    channel = Column(String, nullable=False)
    generated_content = Column(Text, nullable=False)
    attachment_url = Column(String, nullable=True)
    status = Column(SAEnum(ContentStatus), default=ContentStatus.DRAFTED, nullable=False)
    discord_message_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    published_at = Column(DateTime, nullable=True)

    content_item = relationship("ContentItem", back_populates="posts")


class StyleProfile(Base):
    __tablename__ = "style_profiles"

    id = Column(String, primary_key=True, default=new_uuid)
    name = Column(String, nullable=False, unique=True)
    tone = Column(String, default="energetic, technical, clear")
    sentence_length = Column(String, default="medium")
    technical_depth = Column(String, default="intermediate")
    humor_level = Column(String, default="light")
    emoji_usage = Column(String, default="moderate")
    formality = Column(String, default="conversational")
    vocabulary = Column(JSON, nullable=True)
    structure = Column(JSON, nullable=True)
    preferred_expressions = Column(JSON, nullable=True)
    things_to_avoid = Column(JSON, nullable=True)
    full_attributes = Column(JSON, nullable=True)
    example_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    examples = relationship("StyleExample", back_populates="profile")


class StyleExample(Base):
    __tablename__ = "style_examples"

    id = Column(String, primary_key=True, default=new_uuid)
    profile_id = Column(String, ForeignKey("style_profiles.id"), nullable=True)
    category = Column(String, default="general")
    content = Column(Text, nullable=False)
    source_label = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    profile = relationship("StyleProfile", back_populates="examples")


class Source(Base):
    """Configured content sources (RSS feeds, X searches, etc.)."""
    __tablename__ = "sources"

    id = Column(String, primary_key=True, default=new_uuid)
    name = Column(String, nullable=False, unique=True)
    source_type = Column(SAEnum(SourceType), nullable=False)
    url = Column(String, nullable=True)
    query = Column(String, nullable=True)
    category = Column(SAEnum(ContentCategory), default=ContentCategory.GENERAL)
    is_enabled = Column(Boolean, default=True)
    last_fetched = Column(DateTime, nullable=True)
    fetch_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    config = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, server_default=func.now(), index=True)
    tool = Column(String, nullable=True)
    source = Column(String, nullable=True)
    action = Column(String, nullable=False)
    entity_id = Column(String, nullable=True)
    entity_type = Column(String, nullable=True)
    input_hash = Column(String, nullable=True)
    output_status = Column(String, nullable=True)
    error = Column(Text, nullable=True)
    extra_data = Column(JSON, nullable=True)


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id = Column(String, primary_key=True, default=new_uuid)
    name = Column(String, nullable=False, unique=True)
    job_type = Column(String, nullable=False)
    cron_expression = Column(String, nullable=False)
    is_enabled = Column(Boolean, default=True)
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    run_count = Column(Integer, default=0)
    config = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
