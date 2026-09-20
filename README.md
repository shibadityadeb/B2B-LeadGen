# UBM Growth Opportunity Engine — Phase 1

A B2B growth opportunity engine 

**Phase 1:** define a target → discover companies from live web search → store them with source
provenance → run an initial website crawl.

**Phase 2:** research a company → collect public sources → extract evidence → derive business
signals → find publicly listed decision makers → map UBM capabilities → produce an
evidence-backed research brief.

Every claim in the system points back to a source URL and a verbatim excerpt. Opportunities are
presented as **hypotheses to check**, never as established needs.

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

### Phase 2 — company intelligence

6. **Research run** — a per-company pipeline with real stages and progress.
7. **Sources** — Phase 1 pages plus public news, press and event pages, each hashed, typed and
   rated for reliability (first-party > press > third-party > aggregated).
8. **Evidence** — one claim per row, each with a verbatim excerpt, the source URL, a publication
   date where one exists, and an epistemic status (`known` / `inferred` / `possible` / `unknown`).
9. **Signals** — evidence grouped into business signals (expansion, marketing, events, hiring,
   partnerships…), retaining every evidence id.
10. **Decision makers** — people published on the company's *own* pages. A role with no published
    name stays unnamed, and an email is stored only when the address literally appears.
11. **Opportunity hypotheses** — UBM capabilities matched to observed signals, with a plain-language
    rationale and the evidence behind it.
12. **Research brief** — a rendered Markdown brief, plus a structured intelligence profile.

---

## How the reasoning is kept honest

This is the part that matters most, so it is worth stating plainly.

| Risk | What the system does |
| --- | --- |
| Inventing facts | Every evidence row stores a **verbatim excerpt**; the UI shows it next to the source URL so any claim can be checked in one click. |
| Industry-specific rules | There are none. Patterns describe *business events* ("opened a store", "is hiring"), and capabilities are matched to **signal types**, not industries. An unseen industry behaves exactly like a familiar one. |
| Opaque AI scores | Confidence is a weighted sum of five named components — source quality, source count, recency, directness, agreement — and the breakdown is stored and shown. It estimates **evidence quality**, not truth. |
| Fake freshness | A page with no publication date yields freshness measured from *retrieval*, which is labelled `est.` in the UI and **discounted** in the confidence score. |
| Overstated conclusions | A hypothesis only reaches `supported` when several signals agree **across more than one source**. A single self-reported page cannot promote it. |
| Silent conflict resolution | Disagreements are recorded as contradictions with every value named, and a contradicted claim can never score `high`. |
| LLM hallucination | The model is never asked what a company needs. It is given retrieved text, and any claim whose excerpt is not present in that text is **discarded** — the run detail page reports how many were dropped. |
| Fabricated contacts | Names come only from first-party pages; emails only from literal text. No address is ever derived from a name. |

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
| `company_sources` | discovery provenance — where each company came from |
| `company_pages` | crawled pages, unique per `(company_id, url)` |
| `research_runs` | one research execution, with live stage and real counters |
| `research_sources` | retrieved documents: content, hash, type, reliability |
| `evidence` | one claim + verbatim excerpt + source, unique per fingerprint |
| `contradictions` | disagreeing sources, one row per disputed attribute |
| `signals` / `signal_evidence` | grouped interpretations and their evidence links |
| `ubm_capabilities` | the capability catalogue — **data, editable at runtime** |
| `opportunities` + link tables | hypotheses, linked to evidence and signals |
| `decision_makers` | publicly listed people, with provenance |
| `research_briefs` | rendered brief + structured intelligence profile |

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
| POST | `/api/companies/{id}/research` | start a research run (202) |
| GET | `/api/companies/{id}/research` | research state, history and brief |
| POST | `/api/companies/research/bulk` | queue research for several companies |
| GET | `/api/companies/{id}/evidence` | evidence, optionally filtered by `ids` |
| GET | `/api/companies/{id}/signals` | derived business signals |
| GET | `/api/companies/{id}/opportunities` | hypotheses with their evidence ids |
| GET | `/api/companies/{id}/decision-makers` | publicly listed people |
| GET | `/api/companies/{id}/research-sources` | retrieved sources |
| GET | `/api/companies/{id}/contradictions` | conflicting public information |
| GET | `/api/companies/{id}/brief` | rendered research brief |
| GET | `/api/research-runs` · `/api/research-runs/{id}` | run history and detail |
| PATCH | `/api/opportunities/{id}` | accept or dismiss a hypothesis |
| GET/POST/PATCH | `/api/ubm/capabilities` | the capability catalogue |
| GET | `/api/ubm/signal-types` | the signal vocabulary a capability can use |

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
| `RESEARCH_MAX_SOURCES` | `25` | documents one research run may discover |
| `RESEARCH_MAX_PAGES_TO_CRAWL` | `14` | documents one research run may fetch |
| `RESEARCH_BATCH_CONCURRENCY` | `2` | companies researched at once in a bulk run |
| `FRESHNESS_RECENT_DAYS` | `30` | recent / active / older / stale thresholds |
| `FRESHNESS_ACTIVE_DAYS` | `90` | |
| `FRESHNESS_OLDER_DAYS` | `365` | |
| `LLM_PROVIDER` | `none` | `none` \| `ollama` — optional, additive only |
| `LLM_MODEL` | `llama3.1:8b` | model name when `LLM_PROVIDER=ollama` |
| `OLLAMA_URL` | `http://localhost:11434` | optional |
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

Covers Phase 1 (domain normalization, deduplication, query generation, target validation,
discovery processing, crawl behaviour, the API contract) and Phase 2 (evidence extraction and
deduplication, freshness, the confidence formula, contradiction handling, signal derivation,
capability matching, decision-maker validation, LLM guard rails, research-run idempotency and
change detection, and the research API).

Mock providers live in `tests/factories_phase2.py`, so no network, database or model is required.

---

## Try Phase 2

1. Open a company that has been crawled, e.g. from **Companies**.
2. Click **Research company** and watch the real stages — sources, evidence, signals, brief.
3. Open **Opportunities**, then **View evidence** on any card to see the excerpts behind it.
4. Open **Decision makers**, **Sources** and **History**.
5. Click **Research company** again: the second run reuses unchanged pages, reports `+0 new
   evidence`, and appears as a separate row in **History**.
6. Select several companies on **Companies** → **Research selected** to queue a batch.

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
- **Publication dates are usually absent.** Most marketing pages do not state one, so freshness
  falls back to retrieval time. This is labelled `est.` in the UI and discounted in confidence,
  but it means "recent" often means "recently seen", not "recently happened".
- **Decision-maker coverage is thin** on sites without a team or press page — which is most small
  retail sites. The system reports nobody rather than guessing; in testing, named people were
  found only where the company publishes them.
- **Company names** inherited from Phase 1 can be listicle titles ("BlueStone Jewellery Shops in
  Indore"), which then appear in generated rationales.
- **Capability matching is broad**: a company with several signals will match most capabilities as
  `candidate`. The `supported` status, which needs multi-source corroboration, is the meaningful
  one.
- **The LLM layer is untested against a live model** in this build — `LLM_PROVIDER=none` is the
  default and every result shown was produced deterministically. The guard rails are covered by
  unit tests with a stub provider.

---

## Phase 3 — recommended next step

Phase 2 ends at the research brief. Phase 3 turns a reviewed hypothesis into outreach, with a
human in the loop at every step. The first increment should be **draft generation behind human
approval**, not sending.

Concretely:

1. Add `outreach_drafts`: `opportunity_id`, `decision_maker_id`, `subject`, `body`,
   `status` (`draft` / `approved` / `rejected` / `sent`), `approved_by`, `evidence_ids`. Keeping
   the evidence ids on the draft means a reviewer can see which observation each sentence rests
   on — the same traceability rule Phase 2 established.
2. Generate drafts only from `supported` opportunities that a human has not dismissed, using the
   existing `LLMProvider` interface with the same verification discipline: any sentence citing a
   fact must map to a stored evidence row.
3. Build the review queue UI first, and leave sending unimplemented until approval works.
4. Only then add a Gmail draft adapter — writing to *drafts*, never sending — behind a
   `DeliveryProvider` interface, so a different mail backend needs no change to the generator.

Before any of that, two Phase 2 improvements are worth more than new features: obtaining real
publication dates (sitemaps, `article:published_time` meta tags, JSON-LD) so freshness stops
resting on retrieval time, and narrowing capability matching so `candidate` is more selective.
