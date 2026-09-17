from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Story
from .reframe import CATEGORIES
from .schemas import SourceLink, StoryOut

router = APIRouter()


def _to_story_out(story: Story) -> StoryOut:
    sources = [SourceLink(**s) for s in json.loads(story.sources_json)]
    return StoryOut(
        id=story.id,
        category=story.category,
        headline=story.headline,
        original_headline=story.original_headline,
        summary=story.summary,
        image_url=story.image_url,
        sources=sources,
        published_at=story.published_at,
        updated_at=story.updated_at,
    )


@router.get("/stories", response_model=list[StoryOut])
def list_stories(
    category: str | None = Query(default=None, description="Filter by category"),
    limit: int = Query(default=50, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(Story).order_by(Story.published_at.desc()).limit(limit)
    if category:
        stmt = stmt.where(Story.category == category)
    stories = db.execute(stmt).scalars().all()
    return [_to_story_out(s) for s in stories]


@router.get("/stories/{story_id}", response_model=StoryOut)
def get_story(story_id: int, db: Session = Depends(get_db)):
    story = db.get(Story, story_id)
    if story is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Story not found")
    return _to_story_out(story)


@router.get("/categories", response_model=list[str])
def list_categories():
    return CATEGORIES
