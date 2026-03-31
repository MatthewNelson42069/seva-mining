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
    format_type: Optional[str] = None
    score: Optional[float] = None
    quality_score: Optional[float] = None
    no_story_flag: bool
    deep_research: Optional[Any] = None
    draft_content: Optional[Any] = None
    compliance_passed: Optional[bool] = None
    created_at: datetime
