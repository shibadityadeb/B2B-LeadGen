from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import companies, runs, system, targets
from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger
from app.workers import jobs  # noqa: F401  (registers job handlers)
from app.workers.queue import shutdown_job_queue

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("starting %s (%s)", settings.app_name, settings.environment)
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/", tags=["system"])
async def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/health"}
