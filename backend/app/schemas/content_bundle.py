from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional, Any


class ContentBundleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    story_headline: str
    story_url: Optional[str] = None
    source_name: Optional[str] = None
    content_type: Optional[str] = None
    score: Optional[float] = None
    quality_score: Optional[float] = None
    no_story_flag: bool
    deep_research: Optional[Any] = None
    draft_content: Optional[Any] = None
    compliance_passed: Optional[bool] = None
    created_at: datetime


class RenderedImage(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    role: str           # "twitter_visual" | "instagram_slide_1" | "instagram_slide_2" | "instagram_slide_3"
    url: str
    generated_at: str   # ISO-8601


class ContentBundleDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    story_headline: str
    story_url: Optional[str] = None
    source_name: Optional[str] = None
    content_type: Optional[str] = None
    score: Optional[float] = None
    quality_score: Optional[float] = None
    no_story_flag: bool
    deep_research: Optional[Any] = None
    draft_content: Optional[Any] = None
    compliance_passed: Optional[bool] = None
    rendered_images: Optional[list[RenderedImage]] = None
    created_at: datetime


class RerenderResponse(BaseModel):
    bundle_id: UUID
    render_job_id: str
    enqueued_at: str    # ISO-8601
