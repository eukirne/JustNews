# The Bright Side

A small, real, auto-updating news site. It pulls real news from public RSS
feeds, clusters stories that cover the same event across outlets, and asks
Claude to reframe each one around what's genuinely constructive in it —
without inventing facts, downplaying real harm, or forcing a positive spin
onto a story that doesn't have one.

## How it works

```
RSS feeds → dedupe/cluster → Claude reframe → SQLite/Postgres → API → frontend
```

1. **Fetch** (`backend/app/feeds.py`) — pulls RSS from BBC, The Guardian, and
   NPR (see the "Sources" note below on Reuters/AP). Uses each entry's
   `<enclosure>`/`media:content` image when present.
2. **Image fallback** (`backend/app/images.py`) — for articles with no feed
   image, fetches the article's `og:image` meta tag, but only after checking
   the site's `robots.txt`. If the site disallows it, or robots.txt can't be
   fetched, it skips that image rather than scraping anyway.
3. **Dedupe/cluster** (`backend/app/dedupe.py`) — groups articles covering the
   same event using fuzzy title matching within a rolling time window, and
   picks the best-sourced version as the "primary" article to reframe.
4. **Reframe** (`backend/app/reframe.py`) — sends the primary article's title
   + RSS summary to Claude with an editorial system prompt that encodes the
   guardrails below as explicit rules, and gets back a structured
   (headline, summary, category) result via tool use.
5. **Store** (`backend/app/models.py`, `pipeline.py`) — upserts a `Story` row
   per event, keyed by a stable fingerprint so re-running the pipeline
   doesn't duplicate stories already published.
6. **Serve** — FastAPI exposes `/api/stories`; a Next.js frontend polls it
   every few minutes and re-renders without a full page reload.

## Editorial guardrails

Encoded directly in the system prompt in `backend/app/reframe.py`, not left
to vibes:

- Never invent a positive angle that isn't in the source reporting.
- Never omit facts that would change how seriously a reader should take a
  story.
- Ongoing disasters/conflicts: report real casualty/impact figures plainly;
  the constructive angle is the response/aid/accountability/prevention,
  never the event itself.
- If a story genuinely has no constructive angle, present it factually and
  neutrally rather than forcing one.
- Strip loaded partisan language and "us vs. them" framing from policy
  stories; present the substance, not the conflict.
- Never quote more than ~15 words verbatim from a source (copyright).
- Headlines are one-line and factual: no ALL CAPS, no clickbait, no
  manufactured urgency.
- Every story keeps 2–3 original source links for attribution.
- Routine local crime, individual accident reports, and other local-incident
  stories (a single arrest, an inquest into one person's death, a local
  crash, a tribute/obituary piece) are excluded from publication entirely —
  Claude flags these via an `exclude` field on the same reframe call rather
  than a keyword filter, since telling "routine local crime" apart from
  genuinely significant news that happens to involve a crime (a war-crimes
  investigation, a major public-interest trial) takes real judgment. Because
  some reframe calls are "spent" on stories that then get discarded, the
  pipeline oversamples candidate clusters and caps total Claude calls per
  run at `STORIES_PER_REFRESH × 2` (see `pipeline.py`) so a crime-heavy news
  day doesn't blow past the usual per-run cost.
- Sports is a real category with its own feeds, but is hidden from the
  default front-page listing — it only shows up when its tab is selected
  (`/api/stories?category=Sports`; see `DEFAULT_HIDDEN_CATEGORIES` in
  `api.py`).
- Stories with no usable image (no feed-supplied one, and no og:image
  fallback either) are dropped before they'd cost a reframe call
  (`gather_top_clusters` in `pipeline.py`), and the API additionally
  excludes any image-less row from `/api/stories` — so an image is
  guaranteed for everything the site actually shows, whether the story was
  just published or has been sitting in the database for a while.

## A note on sources

BBC, The Guardian, and NPR all have live, free public RSS feeds and are
wired up in `backend/app/config.py` (`FEEDS`). **Reuters and AP both
retired their public RSS feeds years ago** (Reuters in 2020) — they're
still listed in `config.py` as "best effort" entries so the fetcher will
try them and skip cleanly if they 404, but you should expect them not to
return anything unless you have access to a paid feed (Reuters Connect,
an AP entitlement, etc.) to swap in. This is a real gap between what was
originally asked for and what's actually free/legal right now — flagging
it rather than quietly working around it with something that only looks
like Reuters/AP coverage.

## A note on the model

The reframing prompt defaults to `claude-sonnet-5` (`CLAUDE_MODEL` in
`.env`). The original spec asked for `claude-sonnet-4-6`, which isn't a
model ID I can confirm exists — if you have a specific dated snapshot you
want, set `CLAUDE_MODEL` in your `.env` and it'll be used as-is.

## Getting started

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
```

Test the pipeline from the CLI before touching the frontend at all:

```bash
# Fetch + dedupe only — no Claude calls, no DB writes. Good first smoke test.
python -m app.cli fetch --limit 10

# Full pipeline, printed instead of saved — check reframing quality.
python -m app.cli run --dry-run --limit 5

# Full pipeline, saved to SQLite.
python -m app.cli run

# See what's in the database.
python -m app.cli list
```

Run the test suite (uses local fixtures, no network or API calls):

```bash
pytest
```

Run the API server (this also starts the APScheduler job that re-runs the
pipeline every `REFRESH_INTERVAL_MINUTES`):

```bash
uvicorn app.main:app --reload --port 8000
```

If you just want to look at the frontend without a Claude key or working
feeds, seed some fake data instead:

```bash
python scripts/seed_test_data.py
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # point NEXT_PUBLIC_API_URL at your backend
npm run dev
```

### Docker Compose (self-host)

```bash
cp backend/.env.example .env   # then edit; docker-compose reads from repo-root .env
docker compose up --build
```

This runs the backend (SQLite on a named volume) and frontend together.

## Deployment

The backend needs a persistent disk (for SQLite, or point `DATABASE_URL` at
a real Postgres instance) and a long-running process for the scheduler —
that rules out pure serverless functions for it.

- **Render / Fly.io / a small VPS with Docker Compose** — straightforward:
  one persistent web service for the backend, a static/Node service for the
  frontend, no architecture changes needed. This is the path of least
  resistance with what's built here.
- **Vercel** — works well for the Next.js frontend (it's a good fit for
  that half), but Vercel itself has no persistent disk or long-running
  background workers, so the backend would need to move to something like
  Neon/Supabase Postgres for storage and an external cron (e.g. a Vercel
  Cron Job hitting a `/api/refresh` endpoint, or GitHub Actions on a
  schedule) instead of the in-process APScheduler. More moving parts, but
  doable if you want the frontend on Vercel specifically.

Swap `DATABASE_URL` to a `postgresql+psycopg2://...` URL and add
`psycopg2-binary` to `requirements.txt` to move off SQLite for a real
deployment.

### Deploying to Render (step-by-step)

Both Dockerfiles already read the `$PORT` Render assigns, so no extra
config is needed beyond environment variables. Create **two** web
services from the same GitHub repo:

**1. Backend**

- Render dashboard → New → Web Service → connect the `JustNews` repo.
- Root Directory: `backend`. Runtime: Docker (auto-detected from
  `backend/Dockerfile`).
- Health Check Path: `/health`.
- Plan: pick **Starter** (not Free) and attach a **Disk** (1 GB is plenty,
  mount path `/data`). This matters: Render's free web services sleep
  after 15 minutes of inactivity (which kills the in-process scheduler)
  and don't support persistent disks at all, so on Free your SQLite data
  — and the "auto-updating every 30-60 min" behavior — won't actually
  persist or run continuously. Starter is a few dollars a month and fixes
  both.
- Environment variables:
  - `ANTHROPIC_API_KEY` — your key from console.anthropic.com (get one at
    https://console.anthropic.com/settings/keys if you don't have it yet
    — you can deploy without it, the pipeline just won't produce any
    stories until it's set).
  - `CLAUDE_MODEL` — `claude-sonnet-5` (or leave unset to use that default).
  - `DATABASE_URL` — `sqlite:////data/brightside.db`.
  - `STORIES_PER_REFRESH` — `15`.
  - `REFRESH_INTERVAL_MINUTES` — `45`.
  - `CORS_ORIGINS` — leave as `http://localhost:3000` for now; you'll
    update this once the frontend has a URL (step 3 below).
- Deploy, then copy the resulting URL (`https://<something>.onrender.com`).

**2. Frontend**

- New → Web Service → same repo, Root Directory: `frontend`, Docker
  runtime (from `frontend/Dockerfile`).
- Plan: Free is fine here — it can cold-start on a visit without losing
  any data, unlike the backend.
- Environment variables:
  - `NEXT_PUBLIC_API_URL` — the backend URL from step 1. This is read at
    **build time** (it's baked into the client bundle), so if you change
    it later you need to trigger a new deploy, not just a restart.
- Deploy, then copy this URL too.

**3. Wire them together**

- Back on the backend service, update `CORS_ORIGINS` to the frontend's
  URL from step 2, then redeploy the backend (env var changes need a
  redeploy to take effect).
- Visit the frontend URL — you should see stories once the first
  scheduled pipeline run completes (up to `REFRESH_INTERVAL_MINUTES`
  after the backend's first boot, which also kicks one off immediately
  at startup).

## Frontend features

- Editorial layout: hero story + responsive card grid, mobile-friendly.
- Category filter pills (World, UK/Local, Politics, Economy, Science,
  Health, Culture).
- "Show original headlines" toggle for transparency — reveals each
  story's original outlet headline alongside the reframed one.
- Polls the API every 3 minutes via SWR and re-renders without a full page
  reload.
- No moderation queue — stories publish automatically after reframing,
  relying on the prompt's editorial guardrails (per your call on setup;
  easy to add a `status` column + admin approval step later if you change
  your mind).

## Known limitation from building this in a sandboxed session

This project was scaffolded in a network-restricted sandbox that could not
reach any real news site (or api.anthropic.com with a real key), so the
fetch → dedupe → image → reframe pipeline is verified with unit tests
against local fixtures and a seeded-data smoke test of the frontend, but
**not against live feeds or a real Claude call**. Please run
`python -m app.cli fetch` and `python -m app.cli run --dry-run` yourself
once you have a working network + `ANTHROPIC_API_KEY`, and sanity-check a
handful of real reframed stories before flipping on the scheduler — that's
the "confirm reframing quality with me" checkpoint from the original ask,
just moved to your machine since I couldn't do it here.
