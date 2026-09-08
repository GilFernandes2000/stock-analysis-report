from fastapi import APIRouter, Depends

from app.config import settings
from app.services.auth import get_current_user

router = APIRouter(
    prefix="/currency", tags=["currency"], dependencies=[Depends(get_current_user)]
)


@router.get("/supported")
def supported_currencies():
    return {
        "default": settings.default_display_currency,
        "supported": settings.supported_display_currencies,
    }
