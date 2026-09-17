import datetime as dt

from app.articles import RawArticle
from app.dedupe import cluster_articles, normalize_title


def make(outlet, title, hours_offset=0, summary="summary text here"):
    base = dt.datetime(2026, 9, 15, 12, 0, tzinfo=dt.timezone.utc)
    return RawArticle(
        outlet=outlet,
        title=title,
        link=f"https://example.com/{outlet}/{title[:10]}",
        feed_summary=summary,
        published_at=base + dt.timedelta(hours=hours_offset),
        category_hint="World",
    )


def test_normalize_title_strips_outlet_suffix_and_punctuation():
    assert normalize_title("Storm hits coast - BBC News") == "storm hits coast"
    assert normalize_title("Trade deal, signed at last!") == "trade deal signed at last"


def test_same_event_across_outlets_clusters_together():
    articles = [
        make("BBC News", "Storm causes major flooding across coastal towns", 0),
        make("The Guardian World", "Major flooding hits coastal towns after storm", 1),
        make("NPR News", "Coastal towns flooded as storm makes landfall", 2),
        make("BBC News", "Central bank holds interest rates steady", 3),
    ]

    clusters = cluster_articles(articles)

    assert len(clusters) == 2
    flood_cluster = next(c for c in clusters if "flood" in c.primary.title.lower() or any("flood" in m.title.lower() for m in c.members))
    assert len(flood_cluster.members) == 2
    assert set(flood_cluster.outlets) == {"BBC News", "The Guardian World", "NPR News"}


def test_primary_prefers_higher_ranked_outlet():
    articles = [
        make("NPR News", "Regulator fines bank over data breach", 0),
        make("BBC News", "Regulator fines bank over data breach", 1),
    ]

    clusters = cluster_articles(articles)
    assert len(clusters) == 1
    assert clusters[0].primary.outlet == "BBC News"


def test_events_outside_time_window_do_not_cluster():
    articles = [
        make("BBC News", "Wildfire spreads near national park", 0),
        make("The Guardian World", "Wildfire spreads near national park", 40),
    ]

    clusters = cluster_articles(articles)
    assert len(clusters) == 2
