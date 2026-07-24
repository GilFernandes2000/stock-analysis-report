import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ScreenerStockCard } from "../components/StockCard";
import { ErrorNote, LoadingSkeleton, StaleBadge } from "../components/ui";
import { usePageTitle } from "../hooks/usePageTitle";
import type { ScreenerResponse } from "../types";

const PRESET_ORDER = [
  "top_performers",
  "technical_signals",
  "high_conviction",
  "analyst_favorites",
  "europe_germany",
  "europe_uk",
  "europe_france",
] as const;

export function Screener() {
  usePageTitle("Screener");
  const [presets, setPresets] = useState<
    Record<string, { label: string; description: string }>
  >({});
  const [activePreset, setActivePreset] = useState<string>(PRESET_ORDER[0]);
  const [data, setData] = useState<ScreenerResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listScreenerPresets()
      .then(setPresets)
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!activePreset) return;
    setLoading(true);
    setError(null);
    api
      .getScreener(activePreset)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [activePreset]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink">Screener</h1>
        <p className="mt-1 text-sm text-muted">
          Curated Finviz screens for momentum, technical and conviction ideas.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {PRESET_ORDER.map((key) => {
          const meta = presets[key];
          const label = meta?.label ?? key.replace(/_/g, " ");
          return (
            <button
              key={key}
              onClick={() => setActivePreset(key)}
              className={`rounded-xl border px-4 py-2 text-sm font-medium transition ${
                activePreset === key
                  ? "border-accent bg-accent/10 text-accent"
                  : "border-edge text-ink2 hover:border-accent/50 hover:text-ink"
              }`}
            >
              {label}
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
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.stocks.map((stock) => (
            <ScreenerStockCard key={stock.ticker} stock={stock} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
