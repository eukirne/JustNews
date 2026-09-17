from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import pipeline
from app.articles import RawArticle, StoryCluster
from app.models import Base
from app.reframe import ReframedStory


def make_cluster(title: str, hours_offset: int = 0) -> StoryCluster:
    article = RawArticle(
        outlet="BBC News",
        title=title,
        link=f"https://example.com/{title[:10]}",
        feed_summary="summary text",
        published_at=dt.datetime(2026, 9, 15, 12, tzinfo=dt.timezone.utc) + dt.timedelta(hours=hours_offset),
        category_hint="World",
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

    assert [s.headline for s in saved] == ["H1", "H3", "H4"]
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


async def test_run_pipeline_stops_once_limit_reached(tmp_path, monkeypatch):
    clusters = [make_cluster(f"Story {i}", hours_offset=i) for i in range(5)]
    patch_clusters(monkeypatch, clusters)

    responses = [ReframedStory(headline=f"H{i}", summary="S", category="World", exclude=False) for i in range(5)]
    reframer = FakeReframer(responses)
    db = make_db_session(tmp_path)

    saved = await pipeline.run_pipeline(db, limit=2, reframer=reframer)

    assert len(saved) == 2
    assert reframer.calls == 2  # never touched the remaining 3 clusters
