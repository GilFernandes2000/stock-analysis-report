import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings

logger = logging.getLogger(__name__)


def mount_frontend(app: FastAPI) -> None:
    if not settings.serve_frontend:
        return

    dist: Path = settings.frontend_dist_path
    index_file = dist / "index.html"
    assets_dir = dist / "assets"

    if not index_file.is_file():
        logger.warning(
            "Frontend dist not found at %s — run: cd frontend && npm install && npm run build",
            dist,
        )
        return

    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/", include_in_schema=False)
    async def spa_index():
        return FileResponse(index_file)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="Not Found")

        file_path = dist / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)

        return FileResponse(index_file)

    logger.info("Serving frontend from %s", dist)
