# Stock Analysis Report Platform

A Finviz-powered stock analysis dashboard with trend reports, individual stock research, and portfolio insights.

## Features

- **Stock search** — Full analysis for any ticker: fundamentals, technicals, ownership, news sentiment, analyst targets, and Finviz charts
- **Screener** — Browse preset Finviz screens (top performers, technical signals, high conviction, analyst favorites)
- **Trend reports** — Automated screener-based reports with on-demand and scheduled generation
- **Portfolio tracker** — Add/edit holdings, view P&L, sector allocation, and per-stock trend/sentiment summaries
- **Single-server UI** — React dashboard served by FastAPI on one port

See [Architecture](docs/ARCHITECTURE.md) for system flowcharts and data-flow diagrams.

## Disclaimer

Data is sourced from [Finviz](https://finviz.com) via unofficial scraping libraries. Quotes are delayed 15–20 minutes. **This tool is for research and analysis only — not for live trading.**

"People's opinions" in v1 means news headline sentiment (VADER), analyst price targets, and insider activity — not social media sentiment.

## Quick Start (recommended)

One command builds the UI and starts the app on **http://localhost:8000**:

```bash
chmod +x scripts/start.sh
./scripts/start.sh
```

Or manually:

```bash
cd frontend && npm install && npm run build
cd ../backend && source .venv/bin/activate && pip install -e ".[dev]"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000 for the dashboard. API docs: http://localhost:8000/docs

## Docker

```bash
docker compose up --build
```

Open http://localhost:8000

## Optional: Vite dev server

For frontend hot-reload during development:

```bash
# Terminal 1
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 2
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 (proxies `/api` to port 8000).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/stocks/{ticker}` | Full stock analysis |
| GET | `/api/screener/presets` | List screener presets |
| GET | `/api/screener/{preset}` | Run screener preset |
| GET | `/api/reports` | List reports |
| GET | `/api/reports/latest` | Latest report per type |
| POST | `/api/reports/generate` | Generate reports on demand |
| GET/POST/PUT/DELETE | `/api/portfolio` | Portfolio CRUD |
| GET | `/api/portfolio/insights` | Portfolio analysis |

## Scheduled Jobs

Configured in `backend/app/config.py`:

- **Reports:** Weekdays at 11:30 UTC (≈ 6:30 AM ET)
- **Portfolio refresh:** Weekdays at 12:00 UTC (≈ 7:00 AM ET)

## Development

```bash
cd backend && pytest
cd frontend && npm run build
```

## Project Structure

```
stock-analysis-report/
├── backend/          # FastAPI + Finviz services
├── docs/             # Architecture flowcharts
├── frontend/         # React dashboard (built to frontend/dist)
├── scripts/start.sh  # Build UI + run server
└── Dockerfile        # Multi-stage production image
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVE_FRONTEND` | `true` | Serve React build from FastAPI |
| `FRONTEND_DIST_PATH` | `{repo}/frontend/dist` | Path to built frontend |

## Limitations

- Finviz HTML changes can break the scraper; pin `finviz==2.0.0` and upgrade carefully
- Screener/report generation is slow (multiple Finviz requests per stock)
- Single-user SQLite storage (no auth in v1)
