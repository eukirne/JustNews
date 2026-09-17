from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class SourceLink(BaseModel):
    outlet: str
    url: str
    title: str


class StoryOut(BaseModel):
    id: int
    category: str
    headline: str
    original_headline: str
    summary: str
    image_url: str | None
    sources: list[SourceLink]
    published_at: dt.datetime
    updated_at: dt.datetime

    model_config = {"from_attributes": True}
