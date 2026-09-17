from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from .config import get_settings

logger = logging.getLogger("brightside.images")

# One RobotFileParser per host per pipeline run, so we only fetch
# robots.txt once per outlet instead of once per article.
_robots_cache: dict[str, RobotFileParser | None] = {}


async def _get_robots(client: httpx.AsyncClient, base_url: str) -> RobotFileParser | None:
    parsed = urlparse(base_url)
    host = f"{parsed.scheme}://{parsed.netloc}"
    if host in _robots_cache:
        return _robots_cache[host]

    robots_url = urljoin(host, "/robots.txt")
    parser = RobotFileParser()
    try:
        resp = await client.get(robots_url, timeout=get_settings().fetch_timeout_seconds)
        if resp.status_code >= 400:
            # No robots.txt (or it 404s) means no restrictions declared.
            parser.parse([])
        else:
            parser.parse(resp.text.splitlines())
    except httpx.HTTPError:
        # Network failure fetching robots.txt: be conservative and skip
        # this host rather than guess at permission.
        _robots_cache[host] = None
        return None

    _robots_cache[host] = parser
    return parser


async def _allowed(client: httpx.AsyncClient, url: str, user_agent: str) -> bool:
    parser = await _get_robots(client, url)
    if parser is None:
        return False
    return parser.can_fetch(user_agent, url)


async def fetch_og_image(client: httpx.AsyncClient, article_url: str) -> str | None:
    """Best-effort og:image lookup for articles whose feed had no image.

    Respects robots.txt: if the site's robots.txt disallows fetching the
    article path, or robots.txt itself can't be fetched, this returns
    None instead of scraping.
    """
    settings = get_settings()

    if not await _allowed(client, article_url, settings.fetch_user_agent):
        logger.info("robots.txt disallows fetching %s; skipping og:image lookup", article_url)
        return None

    try:
        resp = await client.get(
            article_url,
            headers={"User-Agent": settings.fetch_user_agent},
            timeout=settings.fetch_timeout_seconds,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.info("Could not fetch %s for og:image: %s", article_url, exc)
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    tag = soup.find("meta", attrs={"property": "og:image"}) or soup.find("meta", attrs={"name": "og:image"})
    if tag and tag.get("content"):
        return urljoin(article_url, tag["content"].strip())
    return None


async def fill_missing_images(client: httpx.AsyncClient, articles) -> None:
    """Mutates articles in place, filling image_url via og:image where absent."""
    for article in articles:
        if article.image_url:
            continue
        article.image_url = await fetch_og_image(client, article.link)
