from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .articles import StoryCluster
from .config import FEEDS, get_settings
from .dedupe import cluster_articles, normalize_title
from .feeds import fetch_all_feeds
from .images import choose_best_image, fill_missing_images
from .models import Story
from .reframe import ReframedStory, Reframer

logger = logging.getLogger("brightside.pipeline")

MAX_SOURCES_PER_STORY = 3

# Claude judges two things per candidate on the same reframe call: whether
# it's a personal/individual-focused story to exclude (reframe.py rule 9),
# and how editorially important it is (rule 10, 1-10). Both need real
# judgment rather than a keyword filter — and importance specifically only
# means something if it's judged across a pool bigger than the target
# count, otherwise "most important" degenerates back into "most recent",
# which is the whole behavior this was meant to fix. So the candidate pool
# is oversampled and reframed up to the call budget below (not stopped
# early once `limit` is reached), then only the top `limit` by importance
# are actually published — the rest were still worth reframing to compare
# against, they just didn't make the cut. Total Claude calls per run are
# capped at a multiple of the target story count, bounding worst-case
# spend even on a day heavy with content that gets excluded or outranked.
POOL_MULTIPLIER = 3
MAX_REFRAME_CALLS_MULTIPLIER = 2


@dataclass
class Candidate:
    cluster: StoryCluster
    key: str
    reframed: ReframedStory


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

        # Prefer an image that isn't a close-up face shot or a generic
        # placeholder graphic, checking every outlet's image for the same
        # event (not just the primary's) — see choose_best_image's
        # docstring. This mutates the primary's image_url in place since
        # that's what actually gets stored; it's None when nothing
        # usable was found, and that's fine — stories with no image are
        # still published (text-only), not dropped here.
        for cluster in top:
            cluster.primary.image_url = await choose_best_image(client, cluster)

    return top


async def run_pipeline(db: Session, limit: int | None = None, reframer: Reframer | None = None) -> list[Story]:
    settings = get_settings()
    limit = limit or settings.stories_per_refresh
    max_reframe_calls = limit * MAX_REFRAME_CALLS_MULTIPLIER
    reframer = reframer or Reframer()

    clusters = await gather_top_clusters(limit)
    candidates: list[Candidate] = []
    reframe_calls_made = 0

    # Reframe every fresh candidate up to the call budget — not just
    # enough to fill `limit` — so importance can be judged across the
    # whole pool rather than whichever clusters happened to sort first by
    # recency. This means a run typically spends closer to the full
    # budget than the old "stop as soon as we have enough" behavior did.
    for cluster in clusters:
        if reframe_calls_made >= max_reframe_calls:
            logger.info("Hit the %d-call reframe budget for this run; stopping.", max_reframe_calls)
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
            logger.info("Excluding personal/individual-focused story: %s", cluster.primary.title)
            continue

        candidates.append(Candidate(cluster=cluster, key=key, reframed=reframed))

    # Most important first; recency as the tiebreaker among equally
    # important stories. Only the top `limit` get published — the rest
    # were still worth reframing to compare against, but lose out.
    candidates.sort(key=lambda c: (c.reframed.importance, c.cluster.primary.published_at), reverse=True)
    chosen = candidates[:limit]
    if len(candidates) > limit:
        logger.info("Kept top %d of %d eligible stories by importance", limit, len(candidates))

    saved: list[Story] = []
    for candidate in chosen:
        story = Story(
            cluster_key=candidate.key,
            category=candidate.reframed.category,
            headline=candidate.reframed.headline,
            original_headline=candidate.cluster.primary.title,
            summary=candidate.reframed.summary,
            image_url=candidate.cluster.primary.image_url,
            sources_json=json.dumps(build_sources(candidate.cluster)),
            published_at=candidate.cluster.primary.published_at,
        )
        db.add(story)
        saved.append(story)

    db.commit()
    for story in saved:
        db.refresh(story)
    return saved
