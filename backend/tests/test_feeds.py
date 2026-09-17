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


def test_parse_feed_picks_widest_of_several_media_sizes():
    feed = Feed(name="Sample", url="https://example.com/rss.xml")
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
      <channel>
        <item>
          <title>Multi-size image article</title>
          <link>https://example.com/articles/multi-size</link>
          <description>desc</description>
          <guid>https://example.com/articles/multi-size</guid>
          <media:content url="https://example.com/images/small.jpg" width="140" />
          <media:content url="https://example.com/images/large.jpg" width="1000" />
          <media:content url="https://example.com/images/medium.jpg" width="460" />
        </item>
      </channel>
    </rss>"""

    articles = parse_feed(feed, xml)
    assert len(articles) == 1
    assert articles[0].image_url == "https://example.com/images/large.jpg"


def test_parse_feed_rejects_undersized_thumbnail_only():
    feed = Feed(name="BBC News", url="https://example.com/rss.xml")
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
      <channel>
        <item>
          <title>Tiny thumbnail only article</title>
          <link>https://example.com/articles/tiny-thumb</link>
          <description>desc</description>
          <guid>https://example.com/articles/tiny-thumb</guid>
          <media:thumbnail url="https://example.com/images/tiny.jpg" width="144" height="81" />
        </item>
      </channel>
    </rss>"""

    articles = parse_feed(feed, xml)
    assert len(articles) == 1
    # 144px is below MIN_FEED_IMAGE_WIDTH and there's no larger candidate or
    # enclosure fallback, so no image is published from the feed alone —
    # the og:image fallback in images.py is expected to fill it in instead.
    assert articles[0].image_url is None
