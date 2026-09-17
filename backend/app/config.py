from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Feed(BaseSettings):
    name: str
    url: str
    category_hint: str = "World"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5"

    database_url: str = "sqlite:///./brightside.db"

    @field_validator("claude_model")
    @classmethod
    def _claude_model_looks_like_a_model_id(cls, v: str) -> str:
        # Catches the easy-to-make mistake of pasting DATABASE_URL's value
        # (or any other connection string) into CLAUDE_MODEL by accident —
        # fail loudly at startup instead of silently 404-ing on every
        # single reframe call with a confusing "model: sqlite:///..." error.
        if "://" in v:
            raise ValueError(
                f"CLAUDE_MODEL is set to {v!r}, which looks like a URL/connection "
                "string, not a model ID (e.g. 'claude-sonnet-5'). Check for a "
                "copy-paste mix-up with DATABASE_URL in your environment variables."
            )
        return v

    stories_per_refresh: int = 15
    refresh_interval_minutes: int = 45

    fetch_user_agent: str = "TheBrightSideBot/1.0 (+https://example.com/about-bot)"
    fetch_timeout_seconds: float = 12.0

    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


# Feeds are free, public RSS feeds. BBC/Guardian/NPR are verified working
# public feeds. Reuters and AP both retired their public RSS feeds years
# ago (Reuters in 2020) and now only offer feeds through paid enterprise
# products, so those two are wired up as "best effort": the fetcher will
# try them, log a warning, and skip cleanly if they 404/block rather than
# fail the whole run. Swap in a real URL here if you have access to one
# (e.g. a Reuters Connect feed, or an AP RSS entitlement).
FEEDS: list[Feed] = [
    Feed(name="BBC News", url="http://feeds.bbci.co.uk/news/rss.xml", category_hint="World"),
    Feed(name="BBC News UK", url="http://feeds.bbci.co.uk/news/uk/rss.xml", category_hint="UK/Local"),
    Feed(name="BBC News World", url="http://feeds.bbci.co.uk/news/world/rss.xml", category_hint="World"),
    Feed(name="BBC News Health", url="http://feeds.bbci.co.uk/news/health/rss.xml", category_hint="Health"),
    Feed(name="BBC News Science", url="http://feeds.bbci.co.uk/news/science_and_environment/rss.xml", category_hint="Science"),
    Feed(name="The Guardian World", url="https://www.theguardian.com/world/rss", category_hint="World"),
    Feed(name="The Guardian UK", url="https://www.theguardian.com/uk-news/rss", category_hint="UK/Local"),
    Feed(name="The Guardian Politics", url="https://www.theguardian.com/politics/rss", category_hint="Politics"),
    Feed(name="The Guardian Business", url="https://www.theguardian.com/uk/business/rss", category_hint="Economy"),
    Feed(name="The Guardian Culture", url="https://www.theguardian.com/culture/rss", category_hint="Culture"),
    Feed(name="NPR News", url="https://feeds.npr.org/1001/rss.xml", category_hint="World"),
    Feed(name="NPR World", url="https://feeds.npr.org/1004/rss.xml", category_hint="World"),
    Feed(name="NPR Health", url="https://feeds.npr.org/1128/rss.xml", category_hint="Health"),
    Feed(name="NPR Science", url="https://feeds.npr.org/1007/rss.xml", category_hint="Science"),
    # Best-effort / likely defunct public feeds — kept so the fetcher can
    # confirm (or you can update) their status without a code change elsewhere.
    Feed(name="Reuters Top News", url="https://www.reuters.com/rssFeed/topNews", category_hint="World"),
    Feed(name="AP Top News", url="https://apnews.com/apf-topnews", category_hint="World"),
]


@lru_cache
def get_settings() -> Settings:
    return Settings()
