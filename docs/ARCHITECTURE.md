# Stock Analysis Report — Architecture

Flowcharts for the system overview, user journeys, and core data paths.

## System overview

```mermaid
flowchart TB
    subgraph client [Browser :8000]
        UI[React SPA]
        Pages[Dashboard / Screener / Stock / Portfolio / Reports]
        UI --> Pages
    end

    subgraph server [FastAPI :8000]
        Static[StaticFiles + SPA fallback]
        API["/api/* routes"]
        Scheduler[APScheduler]
        Analysis[AnalysisEngine]
        FinvizSvc[FinvizService]
        Cache[SQLite api_cache]
    end

    subgraph storage [SQLite]
        Holdings[(holdings)]
        Reports[(reports)]
    end

    FinvizWeb[finviz.com]

    Pages -->|fetch /api| API
    Pages -->|GET / assets| Static
    API --> Analysis
    API --> FinvizSvc
    Scheduler -->|weekday cron| API
    Analysis --> FinvizSvc
    FinvizSvc --> Cache
    FinvizSvc --> FinvizWeb
    API --> Holdings
    API --> Reports
```

## User journey

```mermaid
flowchart LR
    Start([Open app]) --> Dashboard[Dashboard]
    Dashboard --> Search{Search ticker?}
    Search -->|Yes| StockDetail[Stock Detail]
    Search -->|No| Browse{Choose section}

    Browse --> Screener[Screener presets]
    Browse --> Portfolio[Portfolio]
    Browse --> Reports[Reports]

    Screener --> StockDetail
    Portfolio --> AddHolding[Add / edit holdings]
    Portfolio --> Insights[Refresh insights]
    Insights --> StockDetail

    Reports --> Generate[Generate reports]
    Generate --> ViewReport[View markdown report]
    ViewReport --> StockDetail

    StockDetail --> Tabs[Overview / Technicals / Ownership / News / Chart]
```

## Stock analysis request flow

```mermaid
sequenceDiagram
    participant User
    participant React as React UI
    participant API as FastAPI
    participant Svc as StockAnalysisService
    participant FV as FinvizService
    participant Cache as SQLite Cache
    participant FZ as finviz.com

    User->>React: Search AAPL
    React->>API: GET /api/stocks/AAPL
    API->>Svc: analyze(AAPL)

    Svc->>FV: get_stock_raw
    FV->>Cache: check cache
    alt cache fresh
        Cache-->>FV: cached data
    else cache miss
        FV->>FZ: scrape stock page
        FZ-->>FV: fundamentals + technicals
        FV->>Cache: store 15min TTL
    end

    Svc->>FV: get_news / analyst_targets / insider
    Svc->>Svc: compute_technical_trend
    Svc->>Svc: VADER sentiment on headlines
    Svc-->>API: StockAnalysisResponse
    API-->>React: JSON payload
    React-->>User: Stock detail tabs + chart
```

## Report generation flow

```mermaid
flowchart TD
    Trigger{Trigger}
    Trigger -->|On demand| UserBtn[User clicks Generate]
    Trigger -->|Scheduled| Cron[APScheduler weekday cron]

    UserBtn --> Builder[ReportBuilder]
    Cron --> Builder

    Builder --> Screener[Finviz Screener preset]
    Screener --> TopN[Top 15 tickers]

    TopN --> Loop[For each ticker]
    Loop --> Analyze[StockAnalysisService.analyze]
    Analyze --> Enrich[Add trend + sentiment + upside]
    Enrich --> Loop

    Loop --> Save[(Save to reports table)]
    Save --> Markdown[Render content_markdown]
    Markdown --> UI[Dashboard / Reports page]
```

## Portfolio insights flow

```mermaid
flowchart TD
    User([User]) --> CRUD[Add / edit / delete holdings]
    CRUD --> DB[(holdings table)]

    User --> Refresh[Refresh insights]
    Refresh --> API[GET /api/portfolio/insights]
    API --> Load[Load all holdings]
    Load --> DB

    Load --> Each[For each ticker]
    Each --> Analyze[StockAnalysisService]
    Analyze --> PnL[Compute P and L]
    Analyze --> Sector[Sector allocation]
    Analyze --> Trend[Trend label per holding]
    Analyze --> Risk[Risk flags]

    PnL --> Response[PortfolioInsightsResponse]
    Sector --> Response
    Trend --> Response
    Risk --> Response
    Response --> UI[Portfolio page]
```

## Currency normalization

```mermaid
flowchart LR
    subgraph fetch [Data sources]
        Yahoo[Yahoo Finance]
        Finviz[Finviz US]
    end

    subgraph normalize [CurrencyService]
        MinorFix["GBp → GBP ÷100"]
        FX["FX to display currency"]
        CacheFX[(api_cache 1h)]
    end

    subgraph ui [UI]
        Selector["Header currency selector"]
        Display["formatMoney in EUR/USD/GBP"]
        Portfolio["Avg cost in display currency"]
    end

    Yahoo --> MinorFix
    Finviz --> MinorFix
    MinorFix --> FX
    CacheFX --> FX
    Selector --> FX
    FX --> Display
    Portfolio --> FX
```

Yahoo returns minor-unit quotes for UK listings (`GBp`, `GBX`). Prices are converted to major units **before** RSI/SMA calculations in `yahoo_client.py`. All API responses include `native_price`, `native_currency`, `display_price`, and `display_currency`. The `price` and `currency` fields mirror display values for backward compatibility.

Portfolio `avg_cost` is stored as a float and interpreted in the user's selected display currency (EUR default).

## Deployment flow

```mermaid
flowchart LR
    subgraph dev [Local dev]
        NPM[npm run build]
        NPM --> Dist[frontend/dist]
        Dist --> Uvicorn[uvicorn :8000]
        Uvicorn --> Browser[http://127.0.0.1:8000]
    end

    subgraph docker [Docker]
        Build[Multi-stage Dockerfile]
        Build --> NodeStage[node: npm build]
        NodeStage --> PyStage[python: copy dist + uvicorn]
        PyStage --> Container[docker compose up]
        Container --> Browser
    end
```

## Key components

| Component | Location | Role |
|-----------|----------|------|
| React SPA | `frontend/src/` | User UI (search, screener, portfolio, reports) |
| FastAPI routes | `backend/app/api/` | REST endpoints |
| FinvizService | `backend/app/services/finviz_client.py` | Scrape Finviz + cache |
| StockAnalysisService | `backend/app/services/stock_analysis.py` | Per-ticker analysis |
| CurrencyService | `backend/app/services/currency_service.py` | Minor-unit fix + FX conversion |
| YahooFinanceClient | `backend/app/services/yahoo_client.py` | European listings + normalized prices |
| ReportBuilder | `backend/app/services/report_builder.py` | Screener-based reports |
| PortfolioService | `backend/app/services/portfolio.py` | Holdings aggregation |
| Static mount | `backend/app/static.py` | Serve `frontend/dist` on port 8000 |
| Scheduler | `backend/app/scheduler/jobs.py` | Weekday report + portfolio jobs |
