from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Story(Base):
    """A single reframed, published story.

    `cluster_key` is a stable fingerprint of the underlying news event
    (derived from the best-sourced article's normalized title + publish
    day) so re-running the pipeline updates the same row instead of
    duplicating it when a story keeps getting covered across runs.
    """

    __tablename__ = "stories"
    __table_args__ = (UniqueConstraint("cluster_key", name="uq_stories_cluster_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cluster_key: Mapped[str] = mapped_column(String(64), index=True)

    category: Mapped[str] = mapped_column(String(32), index=True)
    headline: Mapped[str] = mapped_column(String(300))
    original_headline: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text)

    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # JSON-encoded list of {"outlet": str, "url": str, "title": str}
    sources_json: Mapped[str] = mapped_column(Text)

    published_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc))
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        onupdate=lambda: dt.datetime.now(dt.timezone.utc),
    )
