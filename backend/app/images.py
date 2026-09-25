from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import cv2
import httpx
import numpy as np
from bs4 import BeautifulSoup

from .articles import StoryCluster
from .config import get_settings

logger = logging.getLogger("brightside.images")

_face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

# A detected face bounding box covering at least this fraction of the image
# area is treated as a close-up/zoomed-in portrait shot (e.g. a headshot)
# rather than an editorial photo that merely includes a person somewhere in
# frame. Tuned to catch tight headshot crops without flagging normal wide
# "hero" photography where a face is naturally much smaller in the frame.
FACE_AREA_THRESHOLD = 0.10

# If one quantized color covers at least this fraction of an image's
# pixels, it's treated as a flat graphic/badge (e.g. a generic "BREAKING"
# banner some outlets use as a placeholder og:image before a real photo
# exists) rather than an actual photograph. Real editorial photos almost
# always have far more color variance than this from lighting, shadows,
# and texture.
GENERIC_GRAPHIC_DOMINANT_FRACTION = 0.85

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


def is_face_dominant(image_bytes: bytes) -> bool:
    """Best-effort check for whether an image is a close-up/zoomed face shot.

    This is a soft preference (avoid when possible), not a hard filter, so
    on any decode/detection failure this returns False ("fine to use") —
    an image-processing hiccup should never silently cost us an otherwise
    good story.
    """
    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return False

        height, width = img.shape[:2]
        image_area = height * width
        if image_area == 0:
            return False

        faces = _face_cascade.detectMultiScale(img, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
        if len(faces) == 0:
            return False

        largest_face_area = max(w * h for (_, _, w, h) in faces)
        return bool((largest_face_area / image_area) >= FACE_AREA_THRESHOLD)
    except Exception:
        logger.exception("Face-dominance check failed; treating image as fine to use")
        return False


def is_generic_graphic(image_bytes: bytes, dominant_fraction_threshold: float = GENERIC_GRAPHIC_DOMINANT_FRACTION) -> bool:
    """Best-effort check for a flat, low-complexity graphic (e.g. a generic
    "BREAKING" banner/badge) rather than an actual photograph.

    Unlike is_face_dominant, this is a hard rejection — see
    choose_best_image. On any decode failure, returns False (fine to use),
    the same fail-open behavior as the other image checks here.
    """
    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return False

        small = cv2.resize(img, (64, 64), interpolation=cv2.INTER_AREA)
        pixels = small.reshape(-1, 3).astype(np.int16)
        if len(pixels) == 0:
            return False

        # Quantize so JPEG compression noise doesn't fragment what is
        # visually one flat color into many near-identical ones.
        quantized = (pixels // 16) * 16
        _colors, counts = np.unique(quantized, axis=0, return_counts=True)
        dominant_fraction = counts.max() / len(pixels)
        return bool(dominant_fraction >= dominant_fraction_threshold)
    except Exception:
        logger.exception("Generic-graphic check failed; treating image as fine to use")
        return False


async def choose_best_image(client: httpx.AsyncClient, cluster: StoryCluster) -> str | None:
    """Picks an image for a story, or None if nothing usable is available.

    A clustered story often has an image from more than one outlet (the
    primary article's, plus each covering member's). Each candidate is
    checked in order:

    - A flat/generic graphic (e.g. a placeholder "BREAKING" banner) is
      rejected outright and never used, even as a last resort — showing a
      generic badge instead of a real photo is worse than showing no
      image at all, so a story down to only this kind of "image" is
      published as text-only rather than culled or shown a bad picture.
    - A close-up/zoomed-in face shot is a *soft* preference to avoid: the
      first non-face-dominant, non-generic candidate wins, but if every
      surviving candidate is a face close-up, the best of those is used
      rather than discarding a real photo over that alone.

    Returns None when no candidate survives (no image_url on any article,
    every fetch failed, or every candidate was a generic graphic) — the
    story is still published, just without an image.
    """
    settings = get_settings()
    candidates: list[str] = []
    for article in [cluster.primary, *cluster.members]:
        if article.image_url and article.image_url not in candidates:
            candidates.append(article.image_url)

    face_dominant_fallback: str | None = None

    for url in candidates:
        try:
            resp = await client.get(url, timeout=settings.fetch_timeout_seconds, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.info("Could not fetch candidate image %s: %s", url, exc)
            continue

        content = resp.content
        if is_generic_graphic(content):
            logger.info("Rejecting generic/flat graphic image (e.g. a placeholder banner): %s", url)
            continue

        if not is_face_dominant(content):
            return url

        if face_dominant_fallback is None:
            face_dominant_fallback = url

    return face_dominant_fallback
