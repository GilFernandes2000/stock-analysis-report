from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/currency", tags=["currency"])


@router.get("/supported")
def supported_currencies():
    return {
        "default": settings.default_display_currency,
        "supported": settings.supported_display_currencies,
    }
