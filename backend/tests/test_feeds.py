from pathlib import Path

from app.config import Feed
from app.feeds import parse_feed

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_feed_extracts_articles_and_media_image():
    feed = Feed(name="Sample", url="https://example.com/rss.xml", category_hint="World")
    raw = (FIXTURES / "sample_feed.xml").read_bytes()

    articles = parse_feed(feed, raw)

    assert len(articles) == 2

    flood = articles[0]
    assert flood.title == "City opens new flood defences after last year's storm damage"
    assert flood.outlet == "Sample"
    assert flood.link == "https://example.com/articles/flood-defences"
    assert flood.image_url == "https://example.com/images/flood-defences.jpg"
    assert flood.category_hint == "World"
    assert flood.published_at.year == 2026

    trade = articles[1]
    assert trade.image_url is None
    assert "trade talks" in trade.title.lower()


def test_parse_feed_skips_entries_without_title_or_link():
    feed = Feed(name="Sample", url="https://example.com/rss.xml")
    broken_xml = b"""<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item><title>No link here</title></item>
      <item><link>https://example.com/no-title</link></item>
    </channel></rss>"""

    articles = parse_feed(feed, broken_xml)
    assert articles == []
