"""Configuration and dependency status for the settings page.

Reports reachability only — never secrets, never connection strings.
"""

from __future__ import annotations

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.providers.crawler.registry import get_crawler_provider
from app.providers.search.registry import get_search_provider
from app.workers.queue import get_job_queue



async def _database_status(session: AsyncSession) -> dict:
    try:
        await session.execute(text("SELECT 1"))
        dialect = session.bind.dialect.name if session.bind else "unknown"
        return {
            "name": "Database",
            "provider": f"PostgreSQL ({dialect})" if dialect == "postgresql" else dialect,
            "connected": True,
            "detail": "Connected",
            "optional": False,
        }
    except Exception as exc:
        return {
            "name": "Database",
            "provider": "PostgreSQL",
            "connected": False,
            "detail": f"Not reachable: {type(exc).__name__}",
            "optional": False,
        }


async def _search_status() -> dict:
    try:
        provider = get_search_provider()
        status = await provider.status()
        return {
            "name": "Search Provider",
            "provider": status.name,
            "connected": status.available,
            "detail": status.detail,
            "optional": False,
        }
    except Exception as exc:
        return {
            "name": "Search Provider",
            "provider": settings.search_provider,
            "connected": False,
            "detail": str(exc),
            "optional": False,
        }


async def _crawler_status() -> dict:
    try:
        provider = get_crawler_provider()
        status = await provider.status()
        return {
            "name": "Crawler",
            "provider": status.name,
            "connected": status.available,
            "detail": status.detail,
            "optional": False,
        }
    except Exception as exc:
        return {
            "name": "Crawler",
            "provider": settings.crawler_provider,
            "connected": False,
            "detail": str(exc),
            "optional": False,
        }


async def _ollama_status() -> dict:
    detail = "Optional. Not used by Phase 1 discovery or crawling."
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{settings.ollama_url.rstrip('/')}/api/tags")
        if response.status_code == 200:
            models = [model.get("name") for model in response.json().get("models", [])]
            suffix = f" Models: {', '.join(models[:5])}." if models else " No models pulled."
            return {
                "name": "Local LLM",
                "provider": "ollama",
                "connected": True,
                "detail": detail + suffix,
                "optional": True,
            }
    except httpx.HTTPError:
        pass
    return {
        "name": "Local LLM",
        "provider": "ollama",
        "connected": False,
        "detail": detail + " Not running.",
        "optional": True,
    }


async def collect_status(session: AsyncSession) -> dict:
    components = [
        await _database_status(session),
        await _search_status(),
        await _crawler_status(),
        await _ollama_status(),
    ]
    queue = get_job_queue()
    components.append(
        {
            "name": "Job Queue",
            "provider": getattr(queue, "name", "in_process"),
            "connected": True,
            "detail": f"{queue.pending} job(s) running",
            "optional": False,
        }
    )

    required_ok = all(item["connected"] for item in components if not item["optional"])
    return {
        "healthy": required_ok,
        "environment": settings.environment,
        "components": components,
        "configuration": {
            "search_provider": settings.search_provider,
            "searxng_url": settings.searxng_url,
            "crawler_provider": settings.crawler_provider,
            "ollama_url": settings.ollama_url,
            "max_queries_per_run": settings.search_max_queries_per_run,
            "results_per_query": settings.search_results_per_query,
            "crawl_max_pages": settings.crawl_max_pages,
            "crawl_respect_robots": settings.crawl_respect_robots,
        },
    }
