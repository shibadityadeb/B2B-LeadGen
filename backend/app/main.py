from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    campaigns,
    capabilities,
    companies,
    gmail,
    outreach,
    research,
    runs,
    system,
    targets,
)
from app.core.config import settings
from app.core.db import SessionFactory
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger
from app.services.run_recovery import recover_interrupted_runs
from app.workers import jobs  # noqa: F401  (registers job handlers)
from app.workers.queue import shutdown_job_queue

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("starting %s (%s)", settings.app_name, settings.environment)

    # Background work runs in this process, so a restart or a deploy can kill
    # a run mid-flight. Settle those before serving, or the UI waits forever.
    try:
        async with SessionFactory() as session:
            await recover_interrupted_runs(session)
    except Exception:
        # A database that is not reachable yet must not stop the app booting;
        # the status endpoint will report it.
        logger.exception("could not check for interrupted runs on startup")

    yield
    await shutdown_job_queue()
    logger.info("shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Phase 1: target definition, free prospect discovery, company database "
        "and initial company profiling."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    # Covers hosts that change per deployment, such as Vercel previews.
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.environment != "development" and settings.cors_origin_list == [
    "http://localhost:3000"
]:
    # The single most common deployment mistake: the API is healthy, and the
    # browser blocks every call, so the app looks broken for no visible reason.
    logger.warning(
        "CORS_ORIGINS is still the local default. Browser requests from your "
        "deployed frontend will be blocked. Set CORS_ORIGINS to the frontend "
        "URL, with no trailing slash."
    )


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "details": exc.details},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # `exc.errors()` can carry the original exception object in `ctx`, which
    # is not JSON serializable — encode defensively.
    errors = jsonable_encoder(exc.errors(), custom_encoder={Exception: str})
    return JSONResponse(
        status_code=422,
        content={
            "code": "validation_error",
            "message": "The request payload is invalid.",
            "details": {"errors": errors},
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "code": "internal_error",
            "message": "An unexpected server error occurred.",
            "details": {},
        },
    )


app.include_router(system.router)
app.include_router(targets.router)
app.include_router(runs.router)
app.include_router(companies.router)
app.include_router(research.router)
app.include_router(capabilities.router)
app.include_router(outreach.router)
app.include_router(campaigns.router)
app.include_router(gmail.router)


@app.get("/", tags=["system"])
async def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/health"}
