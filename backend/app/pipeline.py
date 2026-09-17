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

# We ask Claude to flag routine local crime/accident/local-incident stories
# for exclusion (see reframe.py rule 9) rather than filtering by keyword,
# since telling "routine local crime" apart from "nationally significant
# story that happens to involve a crime" needs real judgment. That means
# some reframe calls per run are spent on stories we then discard, so we
# oversample the candidate pool and cap total Claude calls at a multiple of
# the target story count — bounding worst-case spend per run even on a day
# where a large share of the news is exactly what we're filtering out.
POOL_MULTIPLIER = 3
MAX_REFRAME_CALLS_MULTIPLIER = 2


def cluster_key(cluster: StoryCluster) -> str:
    basis = f"{normalize_title(cluster.primary.title)}|{cluster.primary.published_at.date().isoformat()}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


def build_sources(cluster: StoryCluster) -> list[dict]:
    articles = [cluster.primary, *cluster.members][:MAX_SOURCES_PER_STORY]
    return [{"outlet": a.outlet, "url": a.link, "title": a.title} for a in articles]


async def gather_top_clusters(limit: int, pool_multiplier: int = POOL_MULTIPLIER) -> list[StoryCluster]:
    articles = await fetch_all_feeds(FEEDS)
    logger.info("Fetched %d raw articles from %d feeds", len(articles), len(FEEDS))

    clusters = cluster_articles(articles)
    logger.info("Clustered into %d distinct stories", len(clusters))

    top = clusters[: limit * pool_multiplier]

    settings = get_settings()
    async with httpx.AsyncClient(headers={"User-Agent": settings.fetch_user_agent}) as client:
        await fill_missing_images(client, [c.primary for c in top])

    return top


async def run_pipeline(db: Session, limit: int | None = None, reframer: Reframer | None = None) -> list[Story]:
    settings = get_settings()
    limit = limit or settings.stories_per_refresh
    max_reframe_calls = limit * MAX_REFRAME_CALLS_MULTIPLIER
    reframer = reframer or Reframer()

    clusters = await gather_top_clusters(limit)
    saved: list[Story] = []
    reframe_calls_made = 0

    for cluster in clusters:
        if len(saved) >= limit:
            break
        if reframe_calls_made >= max_reframe_calls:
            logger.info(
                "Hit the %d-call reframe budget for this run with only %d stories saved; stopping.",
                max_reframe_calls,
                len(saved),
            )
            break

        key = cluster_key(cluster)
        existing = db.execute(select(Story).where(Story.cluster_key == key)).scalar_one_or_none()
        if existing is not None:
            logger.info("Skipping already-processed story: %s", cluster.primary.title)
            continue

        try:
            reframed = await reframer.reframe(cluster)
            reframe_calls_made += 1
        except Exception:
            logger.exception("Reframing failed for %r, skipping", cluster.primary.title)
            continue

        if reframed.exclude:
            logger.info("Excluding routine crime/local-incident story: %s", cluster.primary.title)
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
