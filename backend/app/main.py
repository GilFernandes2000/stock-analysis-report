import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth,
    currency,
    favorites,
    portfolios,
    reports,
    screener,
    stocks,
)
from app.config import settings
from app.database import init_db
from app.scheduler.jobs import run_scheduled_reports
from app.static import mount_frontend

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def _start_scheduler() -> None:
    scheduler.add_job(
        run_scheduled_reports,
        CronTrigger(
            day_of_week="mon-fri",
            hour=settings.report_cron_hour,
            minute=settings.report_cron_minute,
        ),
        id="daily_reports",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _start_scheduler()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Stock Analysis Report Platform",
    description="Finviz-powered stock analysis, reports, and portfolio insights",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(stocks.router, prefix="/api")
app.include_router(screener.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(portfolios.router, prefix="/api")
app.include_router(favorites.router, prefix="/api")
app.include_router(currency.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


mount_frontend(app)
