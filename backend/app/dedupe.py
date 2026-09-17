from __future__ import annotations

import datetime as dt
import re

from rapidfuzz import fuzz

from .articles import RawArticle, StoryCluster

# Rough source-quality ranking used only to pick which article in a
# cluster becomes the "primary" one sent to Claude for reframing (the
# one with the fullest, most reliable summary). Unlisted outlets default
# to the lowest rank rather than erroring.
OUTLET_RANK = {
    "Reuters Top News": 0,
    "AP Top News": 0,
    "BBC News": 1,
    "BBC News World": 1,
    "BBC News UK": 1,
    "BBC News Health": 1,
    "BBC News Science": 1,
    "The Guardian World": 2,
    "The Guardian UK": 2,
    "The Guardian Politics": 2,
    "The Guardian Business": 2,
    "The Guardian Culture": 2,
    "NPR News": 3,
    "NPR World": 3,
    "NPR Health": 3,
    "NPR Science": 3,
}

_SUFFIX_RE = re.compile(r"\s*[-|]\s*(bbc news|the guardian|npr|reuters|ap news).*$", re.IGNORECASE)
_PUNCT_RE = re.compile(r"[^\w\s]")
_SUFFIXES = ("ing", "ed")

TITLE_SIMILARITY_THRESHOLD = 74
CLUSTER_WINDOW = dt.timedelta(hours=36)


def normalize_title(title: str) -> str:
    title = _SUFFIX_RE.sub("", title)
    title = _PUNCT_RE.sub(" ", title.lower())
    return " ".join(title.split())


def _stem(word: str) -> str:
    for suf in _SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            return word[: -len(suf)]
    return word


def _fuzzy_signature(normalized_title: str) -> str:
    """A coarse, order- and inflection-insensitive signature used only for
    similarity scoring, so 'flooding' vs 'flooded' or reordered clauses
    across outlets don't spuriously prevent a cluster match."""
    return " ".join(sorted(_stem(w) for w in normalized_title.split()))


def _outlet_rank(outlet: str) -> int:
    return OUTLET_RANK.get(outlet, 99)


def _pick_primary(articles: list[RawArticle]) -> RawArticle:
    return min(articles, key=lambda a: (_outlet_rank(a.outlet), -len(a.feed_summary)))


def cluster_articles(articles: list[RawArticle]) -> list[StoryCluster]:
    """Groups articles covering the same event across outlets.

    Uses normalized-title fuzzy matching within a rolling time window
    (same event reported within ~36h of each other). This is a cheap,
    dependency-light stand-in for embedding similarity; it works well
    for hard-news wire-style headlines and is intentionally simple.
    """
    ordered = sorted(articles, key=lambda a: a.published_at)
    clusters: list[list[RawArticle]] = []
    norm_cache: dict[int, str] = {}

    for article in ordered:
        norm = _fuzzy_signature(normalize_title(article.title))
        norm_cache[id(article)] = norm

        best_cluster = None
        best_score = 0.0
        for cluster in clusters:
            last = cluster[-1]
            if article.published_at - last.published_at > CLUSTER_WINDOW:
                continue
            for existing in cluster:
                score = fuzz.token_set_ratio(norm, norm_cache[id(existing)])
                if score > best_score:
                    best_score = score
                    best_cluster = cluster

        if best_cluster is not None and best_score >= TITLE_SIMILARITY_THRESHOLD:
            best_cluster.append(article)
        else:
            clusters.append([article])

    story_clusters: list[StoryCluster] = []
    for group in clusters:
        primary = _pick_primary(group)
        members = [a for a in group if a is not primary]
        story_clusters.append(StoryCluster(primary=primary, members=members))

    story_clusters.sort(key=lambda c: c.primary.published_at, reverse=True)
    return story_clusters
