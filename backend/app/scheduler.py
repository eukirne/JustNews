from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import get_settings
from .db import SessionLocal
from .pipeline import run_pipeline

logger = logging.getLogger("brightside.scheduler")

_scheduler: AsyncIOScheduler | None = None


async def run_pipeline_job() -> None:
    db = SessionLocal()
    try:
        saved = await run_pipeline(db)
        logger.info("Scheduled pipeline run saved %d new stories", len(saved))
    except Exception:
        logger.exception("Scheduled pipeline run failed")
    finally:
        db.close()


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    settings = get_settings()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_pipeline_job,
        "interval",
        minutes=settings.refresh_interval_minutes,
        next_run_time=None,  # first run kicked off explicitly at startup, see main.py
        id="refresh_stories",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
