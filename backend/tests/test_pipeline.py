from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import pipeline
from app.articles import RawArticle, StoryCluster
from app.models import Base
from app.reframe import ReframedStory


def make_cluster(title: str, hours_offset: int = 0, image_url: str | None = None) -> StoryCluster:
    article = RawArticle(
        outlet="BBC News",
        title=title,
        link=f"https://example.com/{title[:10]}",
        feed_summary="summary text",
        published_at=dt.datetime(2026, 9, 15, 12, tzinfo=dt.timezone.utc) + dt.timedelta(hours=hours_offset),
        category_hint="World",
        image_url=image_url,
    )
    return StoryCluster(primary=article, members=[])


class FakeReframer:
    """Returns scripted ReframedStory results (or raises) in call order."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    async def reframe(self, cluster):
        self.calls += 1
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def make_db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    return Session()


def patch_clusters(monkeypatch, clusters):
    async def fake_gather_top_clusters(limit, pool_multiplier=pipeline.POOL_MULTIPLIER):
        return clusters

    monkeypatch.setattr(pipeline, "gather_top_clusters", fake_gather_top_clusters)


async def test_run_pipeline_skips_excluded_stories_and_keeps_going(tmp_path, monkeypatch):
    clusters = [make_cluster(f"Story {i}", hours_offset=i) for i in range(4)]
    patch_clusters(monkeypatch, clusters)

    responses = [
        ReframedStory(headline="H1", summary="S1", category="World", exclude=False),
        ReframedStory(headline="H2", summary="S2", category="World", exclude=True),
        ReframedStory(headline="H3", summary="S3", category="World", exclude=False),
        ReframedStory(headline="H4", summary="S4", category="World", exclude=False),
    ]
    reframer = FakeReframer(responses)
    db = make_db_session(tmp_path)

    saved = await pipeline.run_pipeline(db, limit=3, reframer=reframer)

    # All three non-excluded stories fit within limit=3, so all are kept.
    # Equal (default) importance, so ordered most-recent-first among ties.
    assert {s.headline for s in saved} == {"H1", "H3", "H4"}
    assert reframer.calls == 4  # one call was "wasted" on the excluded story


async def test_run_pipeline_stops_at_reframe_call_budget(tmp_path, monkeypatch):
    # 6 candidate clusters, all excluded — with limit=2 the call budget is
    # limit * MAX_REFRAME_CALLS_MULTIPLIER = 4, so it should give up after
    # 4 calls rather than burning through all 6.
    clusters = [make_cluster(f"Story {i}", hours_offset=i) for i in range(6)]
    patch_clusters(monkeypatch, clusters)

    responses = [ReframedStory(headline=f"H{i}", summary="S", category="World", exclude=True) for i in range(6)]
    reframer = FakeReframer(responses)
    db = make_db_session(tmp_path)

    saved = await pipeline.run_pipeline(db, limit=2, reframer=reframer)

    assert saved == []
    assert reframer.calls == 2 * pipeline.MAX_REFRAME_CALLS_MULTIPLIER


async def test_run_pipeline_keeps_reframing_past_limit_up_to_budget(tmp_path, monkeypatch):
    # 5 candidates, limit=2 -> call budget is limit * MAX_REFRAME_CALLS_MULTIPLIER = 4.
    # Unlike the old "stop as soon as we have `limit`" behavior, it should
    # keep reframing up to the budget so importance can be judged across a
    # wider pool, touching 4 of the 5 clusters (not just 2).
    clusters = [make_cluster(f"Story {i}", hours_offset=i) for i in range(5)]
    patch_clusters(monkeypatch, clusters)

    responses = [ReframedStory(headline=f"H{i}", summary="S", category="World", exclude=False) for i in range(5)]
    reframer = FakeReframer(responses)
    db = make_db_session(tmp_path)

    saved = await pipeline.run_pipeline(db, limit=2, reframer=reframer)

    assert reframer.calls == 4
    # All 4 reframed candidates share the same default importance, so the
    # two most recent (H3, H2) win the tiebreak.
    assert [s.headline for s in saved] == ["H3", "H2"]


async def test_run_pipeline_selects_top_by_importance_not_recency(tmp_path, monkeypatch):
    # Oldest story is the most important one — it should still win over
    # more recent but less important stories, proving selection isn't
    # just "most recent N" anymore.
    clusters = [make_cluster(f"Story {i}", hours_offset=i) for i in range(3)]
    patch_clusters(monkeypatch, clusters)

    responses = [
        ReframedStory(headline="Old-but-important", summary="S", category="World", exclude=False, importance=9),
        ReframedStory(headline="Mid", summary="S", category="World", exclude=False, importance=4),
        ReframedStory(headline="Recent-but-trivial", summary="S", category="World", exclude=False, importance=2),
    ]
    reframer = FakeReframer(responses)
    db = make_db_session(tmp_path)

    saved = await pipeline.run_pipeline(db, limit=2, reframer=reframer)

    assert [s.headline for s in saved] == ["Old-but-important", "Mid"]


async def test_gather_top_clusters_keeps_stories_with_no_image(monkeypatch):
    # Stories without a usable image are published text-only rather than
    # culled — this only checks gather_top_clusters keeps every candidate
    # regardless of what choose_best_image lands on for its image_url.
    clusters = [
        make_cluster("Has image", hours_offset=0, image_url="https://example.com/a.jpg"),
        make_cluster("No image", hours_offset=1, image_url=None),
        make_cluster("Also has image", hours_offset=2, image_url="https://example.com/b.jpg"),
    ]

    async def fake_fetch_all_feeds(feeds):
        return []

    def fake_cluster_articles(articles):
        return clusters

    async def fake_fill_missing_images(client, articles):
        return None

    async def fake_choose_best_image(client, cluster):
        return cluster.primary.image_url  # pass-through: no rejection logic under test here

    monkeypatch.setattr(pipeline, "fetch_all_feeds", fake_fetch_all_feeds)
    monkeypatch.setattr(pipeline, "cluster_articles", fake_cluster_articles)
    monkeypatch.setattr(pipeline, "fill_missing_images", fake_fill_missing_images)
    monkeypatch.setattr(pipeline, "choose_best_image", fake_choose_best_image)

    result = await pipeline.gather_top_clusters(limit=5)

    assert [c.primary.title for c in result] == ["Has image", "No image", "Also has image"]
