import datetime as dt
from pathlib import Path

import cv2
import httpx
import numpy as np
import pytest
import respx

from app import images
from app.articles import RawArticle, StoryCluster

FIXTURES = Path(__file__).parent / "fixtures"


def make_article(outlet: str, image_url: str | None) -> RawArticle:
    return RawArticle(
        outlet=outlet,
        title=f"{outlet} title",
        link=f"https://news.example.com/{outlet}",
        feed_summary="summary",
        published_at=dt.datetime(2026, 9, 15, tzinfo=dt.timezone.utc),
        image_url=image_url,
    )


@pytest.fixture(autouse=True)
def clear_robots_cache():
    images._robots_cache.clear()
    yield
    images._robots_cache.clear()


@pytest.mark.asyncio
@respx.mock
async def test_fetch_og_image_resolves_relative_url_when_allowed():
    respx.get("https://news.example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
    )
    respx.get("https://news.example.com/article-1").mock(
        return_value=httpx.Response(200, text=(FIXTURES / "sample_page.html").read_text())
    )

    async with httpx.AsyncClient() as client:
        url = await images.fetch_og_image(client, "https://news.example.com/article-1")

    assert url == "https://news.example.com/images/hero.jpg"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_og_image_respects_robots_disallow():
    respx.get("https://news.example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /\n")
    )
    # No route registered for the article page itself: if the code tried
    # to fetch it despite the disallow, respx would raise for the
    # unmocked request and fail the test.

    async with httpx.AsyncClient() as client:
        url = await images.fetch_og_image(client, "https://news.example.com/article-1")

    assert url is None


@pytest.mark.asyncio
@respx.mock
async def test_missing_robots_txt_is_treated_as_no_restrictions():
    respx.get("https://news.example.com/robots.txt").mock(return_value=httpx.Response(404))
    respx.get("https://news.example.com/article-1").mock(
        return_value=httpx.Response(200, text=(FIXTURES / "sample_page.html").read_text())
    )

    async with httpx.AsyncClient() as client:
        url = await images.fetch_og_image(client, "https://news.example.com/article-1")

    assert url == "https://news.example.com/images/hero.jpg"


def test_is_face_dominant_handles_garbage_bytes_gracefully():
    assert images.is_face_dominant(b"this is not an image") is False


def test_is_face_dominant_finds_no_faces_in_random_noise():
    noise = np.random.randint(0, 255, (400, 600), dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", noise)
    assert ok
    assert images.is_face_dominant(buf.tobytes()) is False


@pytest.mark.asyncio
@respx.mock
async def test_choose_best_image_prefers_non_face_dominant_candidate(monkeypatch):
    respx.get("https://cdn.example.com/headshot.jpg").mock(return_value=httpx.Response(200, content=b"headshot-bytes"))
    respx.get("https://cdn.example.com/wide-shot.jpg").mock(return_value=httpx.Response(200, content=b"wide-bytes"))

    monkeypatch.setattr(images, "is_face_dominant", lambda data: data == b"headshot-bytes")

    cluster = StoryCluster(
        primary=make_article("BBC News", "https://cdn.example.com/headshot.jpg"),
        members=[make_article("The Guardian", "https://cdn.example.com/wide-shot.jpg")],
    )

    async with httpx.AsyncClient() as client:
        result = await images.choose_best_image(client, cluster)

    assert result == "https://cdn.example.com/wide-shot.jpg"


@pytest.mark.asyncio
@respx.mock
async def test_choose_best_image_falls_back_when_every_candidate_is_face_dominant(monkeypatch):
    respx.get("https://cdn.example.com/headshot.jpg").mock(return_value=httpx.Response(200, content=b"headshot-bytes"))

    monkeypatch.setattr(images, "is_face_dominant", lambda data: True)

    cluster = StoryCluster(primary=make_article("BBC News", "https://cdn.example.com/headshot.jpg"), members=[])

    async with httpx.AsyncClient() as client:
        result = await images.choose_best_image(client, cluster)

    # Avoiding faces is a "when possible" preference — still publish the
    # only available image rather than lose the story entirely.
    assert result == "https://cdn.example.com/headshot.jpg"


@pytest.mark.asyncio
async def test_choose_best_image_returns_none_with_no_candidates():
    cluster = StoryCluster(primary=make_article("BBC News", None), members=[])

    async with httpx.AsyncClient() as client:
        result = await images.choose_best_image(client, cluster)

    assert result is None


def test_is_generic_graphic_handles_garbage_bytes_gracefully():
    assert images.is_generic_graphic(b"this is not an image") is False


def test_is_generic_graphic_detects_a_flat_color_banner():
    solid_red = np.zeros((200, 400, 3), dtype=np.uint8)
    solid_red[:, :] = (0, 0, 200)  # BGR
    ok, buf = cv2.imencode(".jpg", solid_red, [cv2.IMWRITE_JPEG_QUALITY, 90])
    assert ok
    assert images.is_generic_graphic(buf.tobytes()) is True


def test_is_generic_graphic_passes_high_variance_photo():
    noise = np.random.randint(0, 255, (200, 400, 3), dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", noise)
    assert ok
    assert images.is_generic_graphic(buf.tobytes()) is False


@pytest.mark.asyncio
@respx.mock
async def test_choose_best_image_rejects_generic_graphic_even_as_sole_candidate(monkeypatch):
    respx.get("https://cdn.example.com/breaking-banner.jpg").mock(
        return_value=httpx.Response(200, content=b"banner-bytes")
    )

    monkeypatch.setattr(images, "is_generic_graphic", lambda data: True)
    monkeypatch.setattr(images, "is_face_dominant", lambda data: False)

    cluster = StoryCluster(
        primary=make_article("BBC News", "https://cdn.example.com/breaking-banner.jpg"), members=[]
    )

    async with httpx.AsyncClient() as client:
        result = await images.choose_best_image(client, cluster)

    # Unlike face-dominance, this is a hard rejection: no fallback even
    # when it's the only candidate — the story is published without an
    # image rather than with a generic placeholder banner.
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_choose_best_image_prefers_real_photo_over_generic_graphic(monkeypatch):
    respx.get("https://cdn.example.com/breaking-banner.jpg").mock(
        return_value=httpx.Response(200, content=b"banner-bytes")
    )
    respx.get("https://cdn.example.com/real-photo.jpg").mock(return_value=httpx.Response(200, content=b"photo-bytes"))

    monkeypatch.setattr(images, "is_generic_graphic", lambda data: data == b"banner-bytes")
    monkeypatch.setattr(images, "is_face_dominant", lambda data: False)

    cluster = StoryCluster(
        primary=make_article("BBC News", "https://cdn.example.com/breaking-banner.jpg"),
        members=[make_article("The Guardian", "https://cdn.example.com/real-photo.jpg")],
    )

    async with httpx.AsyncClient() as client:
        result = await images.choose_best_image(client, cluster)

    assert result == "https://cdn.example.com/real-photo.jpg"
