import { useEffect, useState } from "react";
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
    priceCurrency: "USD", // Finviz screener quotes are USD
    changePct: s.change_pct,
    marketCap: s.market_cap_value,
    pe: s.pe_value,
  };
}

export function Screener() {
  usePageTitle("Screener");
  const [presets, setPresets] = useState<Record<string, PresetMeta>>({});
  const [order, setOrder] = useState<string[]>([]);
  const [active, setActive] = useState<string>("");
  const [data, setData] = useState<ScreenerResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listScreenerPresets()
      .then((p) => {
        setPresets(p);
        const keys = Object.keys(p);
        setOrder(keys);
        setActive((cur) => cur || keys[0] || "");
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!active) return;
    setLoading(true);
    setError(null);
    api
      .getScreener(active)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [active]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink">Screener</h1>
        <p className="mt-1 text-sm text-muted">
          Curated Finviz screens — sort any column, star a stock to track it, click
          through for full research.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {order.map((key) => {
          const meta = presets[key];
          return (
            <button
              key={key}
              onClick={() => setActive(key)}
              className={`rounded-xl border px-3.5 py-2 text-sm font-medium transition ${
                active === key
                  ? "border-accent bg-accent/10 text-accent"
                  : "border-edge text-ink2 hover:border-accent/50 hover:text-ink"
              }`}
            >
              {meta?.label ?? key.replace(/_/g, " ")}
            </button>
          );
        })}
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
          rows={data.stocks.map(toRow)}
          emptyMessage="No stocks matched this screen right now."
        />
      ) : null}

      <p className="text-[11px] text-muted">
        Screener prices are Finviz USD quotes and may be delayed. European local
        listings (e.g. SAP.DE) are best viewed via search or your portfolio, which
        use Yahoo Finance with native-currency handling.
      </p>
    </div>
  );
}
