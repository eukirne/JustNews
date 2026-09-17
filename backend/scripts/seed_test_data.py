"""Seeds a handful of fake stories for manual/local frontend testing.

Not part of the pipeline — bypasses Claude entirely so you can check the
UI without an API key or network access. Run with:

    DATABASE_URL=sqlite:///./dev.db python scripts/seed_test_data.py
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal, init_db
from app.models import Story

STORIES = [
    dict(
        cluster_key="seed-1",
        category="World",
        headline="Flood barrier finished a season ahead of schedule after last year's storm",
        original_headline="City completes long-delayed flood defences following deadly winter storm",
        summary=(
            "A coastal city has finished a flood barrier project that was fast-tracked after "
            "storms killed three people and flooded hundreds of homes last winter. Engineers say "
            "the new defences are designed to handle a storm surge roughly 40% larger than the one "
            "that caused last year's damage, and residents in the worst-hit streets have already "
            "moved back into repaired homes."
        ),
        image_url=None,
        sources=[
            {"outlet": "BBC News", "url": "https://example.com/bbc/flood-barrier", "title": "City finishes flood barrier"},
            {"outlet": "The Guardian UK", "url": "https://example.com/guardian/flood-barrier", "title": "Flood defences completed early"},
        ],
        published_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2),
    ),
    dict(
        cluster_key="seed-2",
        category="World",
        headline="Aid convoys reach besieged region as death toll from fighting passes 400",
        original_headline="Death toll climbs past 400 as ceasefire allows first aid convoys in weeks",
        summary=(
            "At least 400 people have been killed in the past month of fighting in the region, "
            "according to local health officials, with thousands more displaced. A temporary "
            "ceasefire has allowed the first aid convoys in three weeks to deliver food and medical "
            "supplies, though humanitarian groups say the amount reaching civilians is still far "
            "short of what is needed."
        ),
        image_url=None,
        sources=[
            {"outlet": "Reuters Top News", "url": "https://example.com/reuters/ceasefire", "title": "Ceasefire allows aid convoys"},
            {"outlet": "AP Top News", "url": "https://example.com/ap/ceasefire", "title": "Aid reaches besieged region"},
            {"outlet": "BBC News World", "url": "https://example.com/bbc/ceasefire", "title": "First aid convoys in weeks"},
        ],
        published_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=4),
    ),
    dict(
        cluster_key="seed-3",
        category="Health",
        headline="Trial finds new antibiotic effective against drug-resistant infections",
        original_headline="Breakthrough antibiotic shows promise in fighting superbugs, trial finds",
        summary=(
            "A phase 2 clinical trial found a newly developed antibiotic cleared drug-resistant "
            "bacterial infections in 78% of patients, compared with 45% on existing treatments. "
            "Researchers caution that larger trials are still needed before the drug could be "
            "approved for wider use, and that antibiotic resistance will keep growing without "
            "continued investment in new treatments."
        ),
        image_url=None,
        sources=[
            {"outlet": "NPR Health", "url": "https://example.com/npr/antibiotic", "title": "New antibiotic trial results"},
        ],
        published_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=6),
    ),
    dict(
        cluster_key="seed-4",
        category="Economy",
        headline="Unemployment falls to lowest level in two years as manufacturing hiring picks up",
        original_headline="Jobless rate drops as factories add workers for third straight month",
        summary=(
            "The national unemployment rate fell to 4.1% last month, its lowest level in two "
            "years, driven largely by hiring in manufacturing and construction. Wage growth "
            "remained roughly flat, and economists note the improvement has been concentrated in "
            "a handful of regions, with some rural areas still seeing job losses."
        ),
        image_url=None,
        sources=[
            {"outlet": "The Guardian Business", "url": "https://example.com/guardian/jobs", "title": "Unemployment falls"},
            {"outlet": "NPR News", "url": "https://example.com/npr/jobs", "title": "Jobless rate at two-year low"},
        ],
        published_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=8),
    ),
    dict(
        cluster_key="seed-5",
        category="Science",
        headline="Astronomers confirm water vapour in atmosphere of nearby exoplanet",
        original_headline="Telescope detects water vapour on exoplanet 120 light years away",
        summary=(
            "Using new spectroscopic data, astronomers have confirmed water vapour in the "
            "atmosphere of a planet orbiting a star 120 light years from Earth. The planet is too "
            "hot to support life as we know it, but researchers say the detection method could "
            "help identify potentially habitable worlds in future surveys."
        ),
        image_url=None,
        sources=[
            {"outlet": "BBC News Science", "url": "https://example.com/bbc/exoplanet", "title": "Water vapour found on exoplanet"},
        ],
        published_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=10),
    ),
]


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        for entry in STORIES:
            existing = db.query(Story).filter_by(cluster_key=entry["cluster_key"]).one_or_none()
            if existing:
                continue
            db.add(
                Story(
                    cluster_key=entry["cluster_key"],
                    category=entry["category"],
                    headline=entry["headline"],
                    original_headline=entry["original_headline"],
                    summary=entry["summary"],
                    image_url=entry["image_url"],
                    sources_json=json.dumps(entry["sources"]),
                    published_at=entry["published_at"],
                )
            )
        db.commit()
        print(f"Seeded {db.query(Story).count()} total stories.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
