from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from .config import get_settings
from .db import SessionLocal, init_db
from .pipeline import gather_top_clusters, run_pipeline
from .reframe import Reframer


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(levelname)s %(name)s: %(message)s")


async def cmd_fetch(args: argparse.Namespace) -> None:
    """Fetch + dedupe only, no Claude calls, no DB writes. Good first smoke test."""
    clusters = await gather_top_clusters(args.limit)
    for i, cluster in enumerate(clusters, 1):
        print(f"\n[{i}] {cluster.primary.title}")
        print(f"    outlet(s): {', '.join(cluster.outlets)}")
        print(f"    published: {cluster.primary.published_at.isoformat()}")
        print(f"    image: {cluster.primary.image_url or '(none found)'}")
        print(f"    link: {cluster.primary.link}")


async def cmd_run(args: argparse.Namespace) -> None:
    """Full pipeline: fetch -> dedupe -> reframe. --dry-run skips the DB write
    so you can eyeball reframing quality before it touches the database."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        print("ERROR: ANTHROPIC_API_KEY is not set (check your .env). Aborting.", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        limit = args.limit or settings.stories_per_refresh
        clusters = await gather_top_clusters(limit)
        reframer = Reframer()
        results = []
        for i, cluster in enumerate(clusters, 1):
            try:
                reframed = await reframer.reframe(cluster)
            except Exception as exc:  # noqa: BLE001
                print(f"[{i}] FAILED to reframe {cluster.primary.title!r}: {exc}")
                continue
            results.append((cluster, reframed))

        # Mirror run_pipeline's actual selection: importance first (ties
        # broken by recency), only the top `limit` non-excluded ones would
        # really get published — everything else is shown too, so you can
        # see what got outranked or excluded and judge whether that's right.
        included = [(c, r) for c, r in results if not r.exclude]
        excluded = [(c, r) for c, r in results if r.exclude]
        included.sort(key=lambda pair: (pair[1].importance, pair[0].primary.published_at), reverse=True)
        published, dropped = included[:limit], included[limit:]

        def _print(cluster, reframed, tag: str) -> None:
            print(f"\n[{tag}] importance={reframed.importance} {reframed.category} — {reframed.headline}")
            print(f"    {reframed.summary}")
            print(f"    original headline: {cluster.primary.title}")
            print(f"    sources: {', '.join(cluster.outlets)}")

        for cluster, reframed in published:
            _print(cluster, reframed, "PUBLISH")
        for cluster, reframed in dropped:
            _print(cluster, reframed, "outranked")
        for cluster, reframed in excluded:
            _print(cluster, reframed, "excluded")

        print(f"\n{len(published)} would publish, {len(dropped)} outranked, {len(excluded)} excluded, out of {len(results)} reframed.")
        return

    init_db()
    db = SessionLocal()
    try:
        saved = await run_pipeline(db, limit=args.limit)
    finally:
        db.close()

    print(f"Saved {len(saved)} new stories.")
    for story in saved:
        print(f"  [{story.category}] {story.headline}")


async def cmd_list(args: argparse.Namespace) -> None:
    from .models import Story

    init_db()
    db = SessionLocal()
    try:
        stories = db.query(Story).order_by(Story.published_at.desc()).limit(args.limit).all()
        for story in stories:
            print(json.dumps({
                "id": story.id,
                "category": story.category,
                "headline": story.headline,
                "original_headline": story.original_headline,
                "summary": story.summary,
                "image_url": story.image_url,
                "sources": json.loads(story.sources_json),
                "published_at": story.published_at.isoformat(),
            }, indent=2))
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="justnews", description="Just News pipeline CLI")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="Fetch + dedupe feeds only (no Claude calls, no DB writes)")
    p_fetch.add_argument("--limit", type=int, default=15)
    p_fetch.set_defaults(func=cmd_fetch)

    p_run = sub.add_parser("run", help="Run the full pipeline")
    p_run.add_argument("--limit", type=int, default=None)
    p_run.add_argument("--dry-run", action="store_true", help="Reframe and print, but don't write to the database")
    p_run.set_defaults(func=cmd_run)

    p_list = sub.add_parser("list", help="List stories currently in the database")
    p_list.add_argument("--limit", type=int, default=20)
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    _setup_logging(args.verbose)
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
