from __future__ import annotations

import asyncio
import calendar
import datetime as dt
import logging

import feedparser
import httpx

from .articles import RawArticle
from .config import Feed, get_settings

logger = logging.getLogger("brightside.feeds")

# Below this width (px), a feed-supplied thumbnail is treated as unusable
# rather than published as-is — BBC's RSS, for example, only ever supplies
# a single 144x81 media:thumbnail, which looks visibly blurry stretched to
# fill a card. When every candidate is this small (or none declare a
# width), we return None here so the og:image fallback in images.py fetches
# the article's actual hero image instead.
MIN_FEED_IMAGE_WIDTH = 400


def _entry_published_at(entry) -> dt.datetime:
    for key in ("published_parsed", "updated_parsed"):
        struct = entry.get(key)
        if struct:
            return dt.datetime.fromtimestamp(calendar.timegm(struct), tz=dt.timezone.utc)
    return dt.datetime.now(dt.timezone.utc)


def _entry_image(entry) -> str | None:
    # media:content / media:thumbnail (feedparser exposes both the same way).
    # A feed may list several sizes of the same image (Guardian commonly
    # does); collect every candidate and pick the widest rather than
    # whichever happens to come first.
    candidates: list[tuple[int, str]] = []
    for key in ("media_content", "media_thumbnail"):
        for item in entry.get(key) or []:
            url = item.get("url")
            if not url:
                continue
            try:
                width = int(item.get("width") or 0)
            except (TypeError, ValueError):
                width = 0
            candidates.append((width, url))

    if candidates:
        best_width, best_url = max(candidates, key=lambda c: c[0])
        # width == 0 means no size was declared at all — accept it, since
        # we have no basis to reject it (e.g. NPR's media:content).
        if best_width == 0 or best_width >= MIN_FEED_IMAGE_WIDTH:
            return best_url

    # <enclosure> pointing at an image
    for enc in entry.get("enclosures") or []:
        href = enc.get("href")
        enc_type = (enc.get("type") or "").lower()
        if href and (enc_type.startswith("image/") or not enc_type):
            return href

    return None


def parse_feed(feed: Feed, raw_bytes: bytes) -> list[RawArticle]:
    parsed = feedparser.parse(raw_bytes)
    articles: list[RawArticle] = []
    for entry in parsed.entries:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        if not title or not link:
            continue
        summary = (entry.get("summary") or entry.get("description") or "").strip()
        articles.append(
            RawArticle(
                outlet=feed.name,
                title=title,
                link=link,
                feed_summary=summary,
                published_at=_entry_published_at(entry),
                image_url=_entry_image(entry),
                category_hint=feed.category_hint,
                guid=entry.get("id") or link,
            )
        )
    return articles


async def fetch_feed(client: httpx.AsyncClient, feed: Feed) -> list[RawArticle]:
    settings = get_settings()
    try:
        resp = await client.get(
            feed.url,
            headers={"User-Agent": settings.fetch_user_agent, "Accept": "application/rss+xml, application/xml, text/xml, */*"},
            timeout=settings.fetch_timeout_seconds,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Skipping feed %s (%s): %s", feed.name, feed.url, exc)
        return []

    try:
        return parse_feed(feed, resp.content)
    except Exception:
        logger.exception("Failed to parse feed %s (%s)", feed.name, feed.url)
        return []


async def fetch_all_feeds(feeds: list[Feed]) -> list[RawArticle]:
    settings = get_settings()
    async with httpx.AsyncClient(headers={"User-Agent": settings.fetch_user_agent}) as client:
        per_feed = await asyncio.gather(*(fetch_feed(client, feed) for feed in feeds))
        return [article for articles in per_feed for article in articles]
