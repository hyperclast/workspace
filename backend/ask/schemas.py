from datetime import datetime
from typing import List, Optional

from ninja import Schema
from pydantic import Field


class PageReference(Schema):
    """Represents page used in ask response."""

    external_id: str
    title: str
    updated: Optional[datetime] = None
    created: datetime
    modified: datetime

    class Config:
        from_attributes = True


class AskIn(Schema):
    """Request body for ask API endpoint."""

    query: str = Field(..., min_length=1, max_length=10000)
    page_ids: List[str] = Field(default_factory=list)


class AskOut(Schema):
    """Response payload of ask API endpoint."""

    answer: str
    pages: List[PageReference] = Field(default_factory=list)
