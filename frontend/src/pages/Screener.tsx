import { useEffect, useState } from "react";
import { api } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { ScreenerStockCard } from "../components/StockCard";
import { StaleBadge } from "../components/StaleBadge";
import { usePageTitle } from "../hooks/usePageTitle";
import type { ScreenerResponse } from "../types";

const PRESET_ORDER = [
  "top_performers",
  "technical_signals",
  "high_conviction",
  "analyst_favorites",
] as const;

export function Screener() {
  usePageTitle("Screener");
  const [presets, setPresets] = useState<Record<string, { label: string; description: string }>>({});
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
        <h1 className="text-3xl font-bold text-white">Screener</h1>
        <p className="mt-2 text-slate-400">
          Browse Finviz screener presets for trend and momentum ideas.
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
              className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
                activePreset === key
                  ? "bg-emerald-600 text-white"
                  : "border border-slate-700 text-slate-300 hover:bg-slate-900"
              }`}
            >
              {label}
            </button>
          );
        })}
      </div>

      {data && (
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-slate-400">{data.description}</p>
          <span className="text-sm text-slate-500">{data.count} stocks</span>
          {data.stale && <StaleBadge />}
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-red-300">
          {error}
        </div>
      )}

      {loading ? (
        <LoadingSkeleton rows={6} />
      ) : data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.stocks.map((stock) => (
            <ScreenerStockCard key={stock.ticker} stock={stock} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
