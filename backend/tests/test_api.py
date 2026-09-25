import datetime as dt
import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Story


def make_app_with_test_db(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    from app import db as db_module
    from app.main import app

    def override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[db_module.get_db] = override_get_db
    return app, TestSession


def test_list_and_get_story(tmp_path):
    app, TestSession = make_app_with_test_db(tmp_path)

    session = TestSession()
    story = Story(
        cluster_key="abc123",
        category="World",
        headline="Coastal flood barrier completed ahead of schedule",
        original_headline="City finishes flood wall after last year's storm",
        summary="A short, honest summary of what happened and what is being done.",
        image_url="https://example.com/img.jpg",
        sources_json=json.dumps([{"outlet": "BBC News", "url": "https://bbc.co.uk/x", "title": "Flood wall done"}]),
        published_at=dt.datetime.now(dt.timezone.utc),
    )
    session.add(story)
    session.commit()
    session.refresh(story)
    story_id = story.id
    session.close()

    client = TestClient(app)

    resp = client.get("/api/stories")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["headline"] == "Coastal flood barrier completed ahead of schedule"
    assert body[0]["sources"][0]["outlet"] == "BBC News"

    resp = client.get(f"/api/stories/{story_id}")
    assert resp.status_code == 200
    assert resp.json()["original_headline"] == "City finishes flood wall after last year's storm"

    resp = client.get("/api/stories/999999")
    assert resp.status_code == 404

    resp = client.get("/api/categories")
    assert resp.status_code == 200
    assert "World" in resp.json()


def test_sports_hidden_from_default_listing_but_visible_via_filter(tmp_path):
    app, TestSession = make_app_with_test_db(tmp_path)

    session = TestSession()
    session.add_all(
        [
            Story(
                cluster_key="world-1",
                category="World",
                headline="World story",
                original_headline="World story original",
                summary="summary",
                image_url="https://example.com/world.jpg",
                sources_json=json.dumps([{"outlet": "BBC News", "url": "https://bbc.co.uk/w", "title": "t"}]),
                published_at=dt.datetime.now(dt.timezone.utc),
            ),
            Story(
                cluster_key="sports-1",
                category="Sports",
                headline="Sports story",
                original_headline="Sports story original",
                summary="summary",
                image_url="https://example.com/sports.jpg",
                sources_json=json.dumps([{"outlet": "BBC Sport", "url": "https://bbc.co.uk/s", "title": "t"}]),
                published_at=dt.datetime.now(dt.timezone.utc),
            ),
        ]
    )
    session.commit()
    session.close()

    client = TestClient(app)

    resp = client.get("/api/stories")
    assert resp.status_code == 200
    categories = [s["category"] for s in resp.json()]
    assert "Sports" not in categories
    assert "World" in categories

    resp = client.get("/api/stories?category=Sports")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["headline"] == "Sports story"


def test_stories_without_an_image_are_still_included(tmp_path):
    app, TestSession = make_app_with_test_db(tmp_path)

    session = TestSession()
    session.add_all(
        [
            Story(
                cluster_key="with-image",
                category="World",
                headline="Has an image",
                original_headline="original",
                summary="summary",
                image_url="https://example.com/has-image.jpg",
                sources_json=json.dumps([{"outlet": "BBC News", "url": "https://bbc.co.uk/x", "title": "t"}]),
                published_at=dt.datetime.now(dt.timezone.utc),
            ),
            Story(
                cluster_key="no-image",
                category="World",
                headline="Has no image",
                original_headline="original",
                summary="summary",
                image_url=None,
                sources_json=json.dumps([{"outlet": "BBC News", "url": "https://bbc.co.uk/y", "title": "t"}]),
                published_at=dt.datetime.now(dt.timezone.utc),
            ),
        ]
    )
    session.commit()
    session.close()

    client = TestClient(app)

    resp = client.get("/api/stories")
    assert resp.status_code == 200
    body = resp.json()
    headlines = {s["headline"] for s in body}
    # Stories without a usable image are still published (text-only on
    # the frontend), not excluded — only content-based rules (crime/
    # personal stories, Sports on the default listing) filter results.
    assert headlines == {"Has an image", "Has no image"}
    no_image_story = next(s for s in body if s["headline"] == "Has no image")
    assert no_image_story["image_url"] is None
