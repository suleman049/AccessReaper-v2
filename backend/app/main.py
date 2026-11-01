"""
FastAPI application entrypoint for AccessReaper v2.
Serves the API under /api/* and frontend static files under /*.
"""

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.api_v1.api import api_router
from app.core.config import settings
from app.db.session import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("accessreaper")


# In-memory rate limiter for mutating endpoints
# IP/UID -> list of request timestamps
_MUTATING_CALLS: dict[str, list[float]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup validation
    logger.info(
        "Starting %s v%s in %s mode (ENV=%s)",
        settings.PROJECT_NAME,
        settings.VERSION,
        "DRY_RUN" if settings.DRY_RUN else "LIVE",
        settings.ENV,
    )

    if settings.AUTH_MODE == "dev":
        if settings.HOST != "127.0.0.1":
            msg = f"FATAL SECURITY ERROR: AUTH_MODE=dev is strictly prohibited on non-loopback host (bound to {settings.HOST}). Refusing to start."
            logger.critical(msg)
            raise RuntimeError(msg)
        logger.warning("=" * 72)
        logger.warning("!!! WARNING: AccessReaper v2 is running in dev authentication mode on 127.0.0.1 !!!")
        logger.warning("=" * 72)

    # Initialize DB schema and append-only SQLite triggers
    init_db()
    logger.info("Database schema initialized and immutability triggers enforced.")

    # Initialize and start in-process audit scheduler
    from app.core.scheduler import init_scheduler, shutdown_scheduler

    init_scheduler()
    logger.info("In-process APScheduler initialized.")

    yield
    shutdown_scheduler()
    logger.info("Shutting down %s.", settings.PROJECT_NAME)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)


# Middleware: Request ID and Security Headers
@app.middleware("http")
async def security_and_tracing_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    # Rate limiting on mutating endpoints
    if request.method in (
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    ) and request.url.path.startswith("/api/"):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        calls = _MUTATING_CALLS.setdefault(client_ip, [])
        # Keep only calls from the last 60 seconds
        _MUTATING_CALLS[client_ip] = [t for t in calls if now - t < 60.0]
        if len(_MUTATING_CALLS[client_ip]) >= settings.MUTATING_RATE_LIMIT_PER_MINUTE:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please wait a moment.",
                    }
                },
                headers={"Retry-After": "60", "X-Request-ID": req_id},
            )
        _MUTATING_CALLS[client_ip].append(now)

    response: Response = await call_next(request)

    # Attach tracing and security headers
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Disable static asset caching during development
    if settings.ENV == "dev":
        path_lower = request.url.path.lower()
        if path_lower.endswith((".js", ".css", ".html")) or path_lower in ("/", ""):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"

    # CSP supporting Bootstrap CDN and Firebase SDK scripts
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://www.gstatic.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https:; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "connect-src 'self' https://*.googleapis.com https://*.firebaseio.com https://identitytoolkit.googleapis.com https://securetoken.googleapis.com; "
        "frame-ancestors 'none';"
    )
    response.headers["Content-Security-Policy"] = csp

    return response


# Standardized error responses
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        content = exc.detail
    else:
        content = {
            "error": {
                "code": exc.detail if isinstance(exc.detail, str) else "HTTP_ERROR",
                "message": str(exc.detail),
            }
        }
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    first_err = errors[0] if errors else {}
    msg = f"{first_err.get('loc', ['field'])[-1]}: {first_err.get('msg', 'Invalid input')}"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": {"code": "VALIDATION_ERROR", "message": msg}},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server exception: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred.",
            }
        },
    )


# Mount API routes
app.include_router(api_router, prefix="/api")

# Mount frontend static files
frontend_path = settings.FRONTEND_DIR
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    logger.warning("Frontend directory not found at %s", frontend_path)
