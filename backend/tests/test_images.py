from pathlib import Path

import httpx
import pytest
import respx

from app import images

FIXTURES = Path(__file__).parent / "fixtures"


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
