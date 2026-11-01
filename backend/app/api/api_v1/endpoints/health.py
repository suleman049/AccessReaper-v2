"""
Health check endpoint. No authentication required.
"""

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "product": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "mode": "DRY_RUN" if settings.DRY_RUN else "LIVE",
        "env": settings.ENV,
    }
