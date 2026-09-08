import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { StockTable, type TableRow } from "../components/StockTable";
import { ErrorNote, LoadingSkeleton, StaleBadge } from "../components/ui";
import { usePageTitle } from "../hooks/usePageTitle";
import type { PresetMeta, ScreenerResponse, ScreenerStockRow } from "../types";

function toRow(s: ScreenerStockRow): TableRow {
  return {
    ticker: s.ticker,
    name: s.company,
    sector: s.sector,
    price: s.price_value,
    priceCurrency: "USD",
    changePct: s.change_pct,
    marketCap: s.market_cap_value,
    pe: s.pe_value,
  };
}

const FALLBACK: Record<string, PresetMeta> = {
  top_gainers: { label: "Top Gainers", description: "Largest daily gains" },
  top_losers: { label: "Top Losers", description: "Largest daily declines" },
  most_active: { label: "Most Active", description: "Highest trading volume today" },
};

export function Market() {
  usePageTitle("Market");
  const [movers, setMovers] = useState<Record<string, PresetMeta>>(FALLBACK);
  const [order, setOrder] = useState<string[]>(Object.keys(FALLBACK));
  const [active, setActive] = useState<string>("top_gainers");
  const [data, setData] = useState<ScreenerResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listMovers()
      .then((m) => {
        if (Object.keys(m).length) {
          setMovers(m);
          setOrder(Object.keys(m));
        }
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .getScreener(active)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [active]);

  // Default sort: gainers by change desc handled inside table; keep marketCap
  // for "most active" so size leads. Change is most relevant for movers.
  const defaultSort = active === "most_active" ? "marketCap" : "changePct";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink">Market</h1>
        <p className="mt-1 text-sm text-muted">
          Today's movers across US mid- and large-caps. Star anything to add it to
          your Favorites, or search a ticker above for full research.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {order.map((key) => (
          <button
            key={key}
            onClick={() => setActive(key)}
            className={`rounded-xl border px-3.5 py-2 text-sm font-medium transition ${
              active === key
                ? "border-accent bg-accent/10 text-accent"
                : "border-edge text-ink2 hover:border-accent/50 hover:text-ink"
            }`}
          >
            {movers[key]?.label ?? key.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      {data && (
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-sm text-ink2">{data.description}</p>
          <span className="text-xs text-muted">{data.count} stocks</span>
          {data.stale && <StaleBadge />}
        </div>
      )}

      {error && <ErrorNote message={error} />}

      {loading ? (
        <LoadingSkeleton rows={6} />
      ) : data ? (
        <StockTable
          key={active}
          rows={data.stocks.map(toRow)}
          defaultSort={defaultSort}
          emptyMessage="No movers to show right now."
        />
      ) : null}

      <p className="text-xs text-muted">
        Looking for saved screening reports and portfolio tearsheets? See{" "}
        <Link to="/reports" className="text-accent hover:underline">
          Reports
        </Link>
        .
      </p>
    </div>
  );
}
