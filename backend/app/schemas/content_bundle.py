from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ContentBundleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    story_headline: str
    story_url: str | None = None
    source_name: str | None = None
    content_type: str | None = None
    score: float | None = None
    quality_score: float | None = None
    no_story_flag: bool
    deep_research: Any | None = None
    draft_content: Any | None = None
    compliance_passed: bool | None = None
    created_at: datetime


class ContentBundleDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    story_headline: str
    story_url: str | None = None
    source_name: str | None = None
    content_type: str | None = None
    score: float | None = None
    quality_score: float | None = None
    no_story_flag: bool
    deep_research: Any | None = None
    draft_content: Any | None = None
    compliance_passed: bool | None = None
    created_at: datetime
