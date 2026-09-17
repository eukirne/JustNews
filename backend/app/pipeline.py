from __future__ import annotations

import hashlib
import json
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .articles import StoryCluster
from .config import FEEDS, get_settings
from .dedupe import cluster_articles, normalize_title
from .feeds import fetch_all_feeds
from .images import fill_missing_images
from .models import Story
from .reframe import Reframer

logger = logging.getLogger("brightside.pipeline")

MAX_SOURCES_PER_STORY = 3


def cluster_key(cluster: StoryCluster) -> str:
    basis = f"{normalize_title(cluster.primary.title)}|{cluster.primary.published_at.date().isoformat()}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


def build_sources(cluster: StoryCluster) -> list[dict]:
    articles = [cluster.primary, *cluster.members][:MAX_SOURCES_PER_STORY]
    return [{"outlet": a.outlet, "url": a.link, "title": a.title} for a in articles]


async def gather_top_clusters(limit: int) -> list[StoryCluster]:
    articles = await fetch_all_feeds(FEEDS)
    logger.info("Fetched %d raw articles from %d feeds", len(articles), len(FEEDS))

    clusters = cluster_articles(articles)
    logger.info("Clustered into %d distinct stories", len(clusters))

    top = clusters[:limit]

    settings = get_settings()
    async with httpx.AsyncClient(headers={"User-Agent": settings.fetch_user_agent}) as client:
        await fill_missing_images(client, [c.primary for c in top])

    return top


async def run_pipeline(db: Session, limit: int | None = None, reframer: Reframer | None = None) -> list[Story]:
    settings = get_settings()
    limit = limit or settings.stories_per_refresh
    reframer = reframer or Reframer()

    clusters = await gather_top_clusters(limit)
    saved: list[Story] = []

    for cluster in clusters:
        key = cluster_key(cluster)
        existing = db.execute(select(Story).where(Story.cluster_key == key)).scalar_one_or_none()
        if existing is not None:
            logger.info("Skipping already-processed story: %s", cluster.primary.title)
            continue

        try:
            reframed = await reframer.reframe(cluster)
        except Exception:
            logger.exception("Reframing failed for %r, skipping", cluster.primary.title)
            continue

        story = Story(
            cluster_key=key,
            category=reframed.category,
            headline=reframed.headline,
            original_headline=cluster.primary.title,
            summary=reframed.summary,
            image_url=cluster.primary.image_url,
            sources_json=json.dumps(build_sources(cluster)),
            published_at=cluster.primary.published_at,
        )
        db.add(story)
        saved.append(story)

    db.commit()
    for story in saved:
        db.refresh(story)
    return saved
