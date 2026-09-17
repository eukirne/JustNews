from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass
class RawArticle:
    """A single article as pulled straight from an RSS feed, pre-dedupe."""

    outlet: str
    title: str
    link: str
    feed_summary: str
    published_at: dt.datetime
    image_url: str | None = None
    category_hint: str = "World"
    guid: str = ""


@dataclass
class StoryCluster:
    """One or more RawArticles judged to be about the same event.

    `primary` is the best-sourced article (longest summary / most
    reputable outlet, see dedupe.py) and is what gets sent to Claude for
    reframing. `members` holds all articles in the cluster so we can
    attribute every outlet that covered the story.
    """

    primary: RawArticle
    members: list[RawArticle] = field(default_factory=list)

    @property
    def outlets(self) -> list[str]:
        seen: list[str] = []
        for a in [self.primary, *self.members]:
            if a.outlet not in seen:
                seen.append(a.outlet)
        return seen
