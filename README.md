# UBM Growth Opportunity Engine — Phase 1

A B2B growth opportunity engine for [Upshot Brand Media](https://www.upshotbrandmedia.com/).

**Phase 1 scope:** define a target → discover companies from live web search → store them with
source provenance → run an initial website crawl. Every company in the database is traceable to
the search result that produced it.

Phase 1 deliberately makes **no opportunity judgements** and uses **no LLM**. It builds the
evidence base that Phase 2 will interpret.

---

## What it does

1. **Targets** — an industry, a location, optional keywords and free-text context. Nothing is
   hardcoded: any industry and any city work identically.
2. **Discovery** — generates search queries from the target, runs them through a search provider,
   stores every raw result, resolves results to canonical domains, discards directories and
   aggregators, deduplicates by domain, and saves companies plus their source URLs.
3. **Company database** — companies, their evidence (`company_sources`) and their crawled pages
   (`company_pages`).
4. **Initial crawl** — fetches the homepage and a handful of standard pages (About, Products,
   Services, Contact, News, Blog, Careers), respecting `robots.txt` and rate limits.
5. **Deterministic summary** — counts and verbatim extracts only. No generated prose.

---

## Requirements

| Component | Version | Notes |
| --- | --- | --- |
| Python | 3.11+ | backend |
| Node.js | 20+ | frontend |
| PostgreSQL | 14+ | locally installed, or a free Supabase project |

There is **no Docker and no Redis** anywhere in this setup. Background jobs run as asyncio tasks
inside the API process, behind a `JobQueue` interface that a real broker can implement later.

---

## Setup

### 1. Environment

```bash
cp .env.example .env
```

Then edit `.env` — at minimum `DATABASE_URL`. See [Environment variables](#environment-variables).

### 2. Database

**Option A — local PostgreSQL**

```bash
brew install postgresql@16 && brew services start postgresql@16
```

```bash
psql -h localhost -d postgres -c "CREATE ROLE ubm LOGIN PASSWORD 'ubm';" -c "CREATE DATABASE ubm OWNER ubm;"
```

**Option B — Supabase free tier**

Create a project, copy the **session pooler** connection string, and set it in `.env` with the
driver prefix swapped to `postgresql+asyncpg://`.

### 3. Backend

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
cd backend && .venv/bin/alembic upgrade head
```

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
```

API docs: <http://localhost:8000/docs>

### 4. Search provider (SearXNG)

SearXNG is a self-hosted metasearch engine — free, no API key, no account. It is installed from
source into its own virtualenv; **this does not use Docker**.

One-time install (a few minutes):

```bash
./infrastructure/searxng/install.sh
```

Start it (leave it running):

```bash
./infrastructure/searxng/start.sh
```

Verify:

```bash
curl "http://127.0.0.1:8888/search?q=test&format=json" | head -c 200
```

> **Why not the zero-setup fallback?** `SEARCH_PROVIDER=duckduckgo` needs nothing installed, but
> the public endpoint bot-challenges repeated automated queries and will usually return nothing
> after the first one. The app reports that as a real error rather than "0 results". Use SearXNG
> for anything beyond a quick look.

### 5. Frontend

```bash
cd frontend && npm install
```

```bash
cd frontend && npm run dev
```

Open <http://localhost:3000>.

---

## Try it

1. Go to **Targets → New target**.
2. Industry `Jewellery`, Location `Indore`, keyword `jewellery showroom`.
3. Click **Preview queries** to see exactly what will be sent to the search provider.
4. **Save target**, then **Run discovery**.
5. Watch the run page: real stages, real counters, the actual queries and results.
6. Open a company → **Research website** → watch the crawl populate pages and sources.

---

## Architecture

```
/
├── backend/                  FastAPI + SQLAlchemy 2.0 (async) + Alembic
│   └── app/
│       ├── api/routes/       HTTP layer only
│       ├── services/         business logic (discovery, crawl, normalization, summary)
│       ├── repositories/     database access
│       ├── providers/        external I/O, swappable
│       │   ├── search/       base.py · searxng.py · duckduckgo.py · registry.py
│       │   └── crawler/      base.py · crawl4ai_crawler.py · httpx_crawler.py · registry.py
│       ├── workers/          job queue interface + in-process implementation
│       ├── models/           SQLAlchemy models
│       ├── schemas/          Pydantic request/response schemas (separate from models)
│       └── core/             config, db, logging, errors
├── frontend/                 Next.js 15 App Router + TypeScript + Tailwind
│   └── public/logo.svg       brand lockup — replace with the original asset
├── infrastructure/searxng/   install.sh · start.sh · settings.yml
├── .env.example
└── README.md
```

**Layering.** `api → services → repositories → providers`. Services never touch HTTP; providers
never touch the database.

**Provider abstraction.** Nothing outside `providers/` imports a concrete provider. Adding a
paid search API in Phase 3 means writing one module and registering it — the discovery pipeline
does not change.

**Job queue.** `JobQueue.enqueue(name, **payload)` is the only thing the API knows. Swapping the
in-process runner for Celery/Arq means implementing one class.

**Politeness.** Page selection, `robots.txt` compliance and rate limiting live in
`services/crawl.py`, not in the providers — so changing the fetch backend cannot accidentally
change crawling behaviour.

### Database schema

| Table | Purpose |
| --- | --- |
| `targets` | what to look for |
| `discovery_runs` | one pipeline execution, with live stage/progress and real counters |
| `search_queries` | the generated queries and their outcome |
| `search_results` | every raw result, kept verbatim, with accept/reject decision |
| `companies` | deduplicated by `canonical_domain` (unique) |
| `company_sources` | **evidence provenance** — where each company came from |
| `company_pages` | crawled pages, unique per `(company_id, url)` |

Indexed on domain, name, industry, location, status, target id, run id and `created_at`.

---

## API

| Method | Path | |
| --- | --- | --- |
| GET | `/api/targets` | list with company counts and last-run status |
| POST | `/api/targets` | create |
| POST | `/api/targets/preview` | preview generated queries, saves nothing |
| GET | `/api/targets/{id}` | |
| DELETE | `/api/targets/{id}` | |
| POST | `/api/targets/{id}/discover` | enqueue a discovery run (202) |
| GET | `/api/runs` | paginated |
| GET | `/api/runs/{id}` | detail incl. queries and results |
| GET | `/api/companies` | paginated + filters |
| GET | `/api/companies/filters` | available filter values |
| GET | `/api/companies/{id}` | detail incl. sources, pages, summary |
| GET | `/api/companies/{id}/sources` | |
| GET | `/api/companies/{id}/pages` | |
| POST | `/api/companies/{id}/crawl` | enqueue a website crawl (202) |
| GET | `/api/dashboard` | real counts |
| GET | `/api/status` | dependency health, never secrets |

Errors are `{ "code": "...", "message": "...", "details": {...} }`.

---

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | — | `postgresql+asyncpg://user:pass@host:5432/db` |
| `SEARCH_PROVIDER` | `searxng` | `searxng` or `duckduckgo` |
| `SEARXNG_URL` | `http://127.0.0.1:8888` | use `127.0.0.1`, not `localhost` |
| `SEARXNG_PORT` / `SEARXNG_SECRET` | `8888` / — | used by `start.sh` |
| `SEARCH_RESULTS_PER_QUERY` | `20` | |
| `SEARCH_MAX_QUERIES_PER_RUN` | `12` | |
| `SEARCH_DELAY_SECONDS` | `1.0` | pause between queries |
| `SEARCH_EXCLUDED_DOMAINS` | — | extra directories to ignore, comma-separated |
| `CRAWLER_PROVIDER` | `auto` | `auto` \| `crawl4ai` \| `httpx` |
| `CRAWL_MAX_PAGES` | `8` | per company |
| `CRAWL_DELAY_SECONDS` | `1.0` | between page fetches |
| `CRAWL_RESPECT_ROBOTS` | `true` | |
| `CRAWL_USER_AGENT` | identifies the crawler | |
| `OLLAMA_URL` | `http://localhost:11434` | optional, **unused by Phase 1 logic** |
| `CORS_ORIGINS` | `http://localhost:3000` | |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | frontend → backend |

Secrets are never stored in the database and never returned by `/api/status`.

### Optional: browser-rendered crawling

Some company sites render entirely in JavaScript; the built-in HTTP crawler retrieves almost no
text from those. To handle them:

```bash
cd backend && .venv/bin/pip install -r requirements-crawl4ai.txt && .venv/bin/playwright install chromium
```

`CRAWLER_PROVIDER=auto` picks Crawl4AI up automatically once installed.

---

## Branding

The sidebar lockup is `frontend/public/logo.svg`, an SVG rebuild of the Upshot Brand Media
wordmark; `frontend/src/app/icon.svg` is the square favicon variant. To use the original brand
files, replace those two files (keeping the names) — nothing else needs to change. The UI accent
colour is the brand blue `#0b54a6`, defined once in `frontend/src/app/globals.css`.

The interface is light-only by design (`color-scheme: light`), and is verified at phone, tablet
and desktop widths.

---

## Tests

```bash
cd backend && .venv/bin/python -m pytest
```

Covers domain normalization, deduplication, query generation, target validation, discovery result
processing, crawl behaviour (including robots.txt and re-crawl idempotency), summary extraction
and the API contract. Runs against in-memory SQLite — no services required.

---

## Known limitations

- **Directory results.** The domain blocklist catches the common aggregators, but new listing
  sites appear constantly and some reach the company list. Add them to `SEARCH_EXCLUDED_DOMAINS`.
- **JavaScript-only sites** yield almost no text without the optional Crawl4AI backend.
- **Company attributes** (`industry`, `location`) are inherited from the target that found the
  company — that is what Phase 1 can honestly assert. Size is never guessed.
- **Company names** come from search result titles, trimmed of common noise. A listicle title can
  produce an awkward name.
- **In-process jobs** run inside the API process; restarting the backend abandons an in-flight
  run (it stays `running` in the database rather than being resumed).
- **Search throughput** is intentionally slow — one query per second — to stay polite.

---

## Phase 2 — recommended next step

The evidence base is in place; the next increment should be **signal extraction over the pages
already crawled**, before adding decision-maker discovery or opportunity matching.

Concretely:

1. Add a `company_signals` table: `company_id`, `signal_type` (expansion, hiring, product launch,
   event, campaign, partnership), `evidence_page_id` → `company_pages.id`, `evidence_excerpt`,
   `detected_at`, `confidence`. The foreign key to the page is the point — **every derived
   insight must be traceable to the source text it came from**.
2. Deepen the crawler to follow News/Blog/Careers listings (the page classifier already labels
   them) with a configurable page budget.
3. Add a `SignalExtractor` provider interface with a deterministic rule-based implementation
   first, then an Ollama-backed one behind the same interface — mirroring the existing
   search/crawler provider pattern, so the LLM stays optional.
4. Only then move to decision-maker discovery and UBM capability matching.
