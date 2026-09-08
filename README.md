# Meridian — Portfolio Intelligence

A multi-user portfolio management and stock research platform. Import your broker
history from **Degiro** or **Trading 212**, track performance with
institutional-grade analytics, and generate professional portfolio tearsheets —
all running locally on one port.

## Features

### Portfolio management
- **Multi-user with authentication** — each user has their own login (PBKDF2-hashed
  passwords, session tokens) and manages any number of portfolios
- **Broker imports** — parse Degiro `Transactions.csv` + `Account.csv` (multilingual
  headers: EN/PT/NL/ES/IT) and Trading 212 history exports; automatic ISIN → Yahoo
  ticker resolution with a manual mapping step in the preview, duplicate detection
  on re-import
- **Transaction-based accounting** — positions, average cost (fees capitalized),
  realized P&L, dividends, fees, taxes, and cash balance are all computed from the
  transaction stream (average-cost method)
- **Analytics engine** — daily portfolio value series (multi-currency, GBp-aware),
  time-weighted return vs a configurable benchmark, annualized volatility, Sharpe,
  max drawdown, beta, sector/currency/country allocation, top contributors and
  detractors, and rule-based risk flags

### Reports
- **Portfolio tearsheets** — Wall-Street-style reports for one or more selected
  portfolios: executive summary, performance vs benchmark, risk assessment,
  allocation, holding-by-holding commentary enriched with live research (trend,
  sentiment, analyst targets), and outlook/action items. Export to PDF via the
  print dialog.
- **Market reports** — scheduled Finviz screener scans (momentum, technical
  signals, high conviction, analyst favorites, Europe) on weekday mornings or on
  demand

### Research
- **Stock search** — US tickers (AAPL) and European listings (SAP.DE, ASML.AS,
  VOD.L…) via Finviz + Yahoo Finance, with technicals, ownership, news sentiment
  (VADER) and analyst targets
- **Screener** — curated Finviz preset screens
- **Display currency** — EUR/USD/GBP with automatic GBp normalization

## Quick start

```bash
chmod +x scripts/start.sh
./scripts/start.sh
```

Open **http://localhost:8000**, create your account, create a portfolio, and
import your broker CSV. API docs: http://localhost:8000/docs

Manual start:

```bash
cd frontend && npm install && npm run build
cd ../backend && python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Getting your broker exports

| Broker | Where to export | What it gives you |
|--------|-----------------|-------------------|
| Degiro | Inbox → Account statements → **Transactions.csv** | All trades (buys/sells, fees) |
| Degiro | Inbox → Account statements → **Account.csv** | Dividends, dividend tax, deposits, withdrawals, fees, interest |
| Trading 212 | History → **Export CSV** (all event types) | Everything in one file |

Import both Degiro files for full analytics. Re-importing the same file is safe —
duplicates are detected and skipped.

## API overview

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` · `/login` · `/logout` | Authentication (Bearer tokens) |
| GET/POST/PUT/DELETE | `/api/portfolios` | Portfolio CRUD (`?quotes=true` for live valuation) |
| GET/POST/DELETE | `/api/portfolios/{id}/transactions` | Transaction management |
| POST | `/api/portfolios/{id}/import/preview` | Parse a broker CSV (multipart) |
| POST | `/api/portfolios/{id}/import/commit` | Persist reviewed rows |
| GET | `/api/portfolios/{id}/analytics` | Full analytics payload |
| POST | `/api/reports/tearsheet` | Generate a tearsheet for selected portfolios |
| GET/POST | `/api/reports` · `/generate` | List reports / run market scans |
| GET | `/api/stocks/{ticker}` | Full stock research (`?currency=EUR`) |
| GET | `/api/screener/{preset}` | Run a Finviz screener preset |

## Development

```bash
cd backend && source .venv/bin/activate && ruff check . && pytest
cd frontend && npm run build                         # type-check + build
```

CI (`.github/workflows/ci.yml`) runs the same checks on every push and PR.

Frontend hot reload: `npm run dev` in `frontend/` (proxies `/api` to :8000).

### Database schema

Schema is managed with **Alembic** (`backend/migrations/`). The app runs
`alembic upgrade head` on startup, so a fresh database is built automatically
and an existing one is migrated; a database that predates Alembic is adopted
and stamped on first boot. To change the schema:

```bash
cd backend && source .venv/bin/activate
# edit models, then:
alembic revision --autogenerate -m "what changed"
alembic upgrade head            # applied automatically on next app start too
```

## Docker

```bash
docker compose up --build
```

## Notes & limitations

- Data comes from Finviz (scraper — pin `finviz==2.0.0`) and Yahoo Finance
  (`yfinance`); quotes are delayed. **Not intended for live trading; not
  investment advice.**
- SQLite storage (`backend/stock_analysis.db`); auth is designed for a trusted
  local/home-server deployment. Login has a best-effort in-process rate limit
  (10 failures per username+IP per 15 min); it runs plain HTTP unless you put it
  behind TLS, and the rate-limit state is per-process (resets on restart, not
  shared across workers).
- An ISIN listed on several exchanges resolves to the listing matching the trade
  currency when Yahoo offers one; otherwise valuation uses the instrument's real
  quote currency with FX conversion (e.g. VUSA bought in EUR still values
  correctly off the GBp LSE listing).
