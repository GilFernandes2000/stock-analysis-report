import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { SectorChart } from "../components/SectorChart";
import { StaleBadge } from "../components/StaleBadge";
import { TrendBadge } from "../components/TrendBadge";
import { usePageTitle } from "../hooks/usePageTitle";
import type { Holding, PortfolioInsights } from "../types";

export function Portfolio() {
  usePageTitle("Portfolio");
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [insights, setInsights] = useState<PortfolioInsights | null>(null);
  const [loading, setLoading] = useState(true);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState({
    ticker: "",
    shares: "",
    avg_cost: "",
    notes: "",
  });

  async function loadHoldings() {
    const data = await api.listHoldings();
    setHoldings(data);
  }

  async function loadInsights() {
    setInsightsLoading(true);
    try {
      const data = await api.portfolioInsights();
      setInsights(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load insights");
    } finally {
      setInsightsLoading(false);
    }
  }

  useEffect(() => {
    loadHoldings()
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  function resetForm() {
    setForm({ ticker: "", shares: "", avg_cost: "", notes: "" });
    setEditingId(null);
    setShowForm(false);
  }

  function startEdit(h: Holding) {
    setEditingId(h.id);
    setShowForm(true);
    setForm({
      ticker: h.ticker,
      shares: String(h.shares),
      avg_cost: String(h.avg_cost),
      notes: h.notes ?? "",
    });
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      if (editingId != null) {
        await api.updateHolding(editingId, {
          shares: parseFloat(form.shares),
          avg_cost: parseFloat(form.avg_cost),
          notes: form.notes || undefined,
        });
      } else {
        await api.createHolding({
          ticker: form.ticker.toUpperCase(),
          shares: parseFloat(form.shares),
          avg_cost: parseFloat(form.avg_cost),
          notes: form.notes || undefined,
        });
      }
      resetForm();
      await loadHoldings();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save holding");
    }
  }

  async function handleDelete(id: number) {
    await api.deleteHolding(id);
    if (editingId === id) resetForm();
    await loadHoldings();
    if (insights) await loadInsights();
  }

  if (loading) return <LoadingSkeleton rows={5} />;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white">Portfolio</h1>
          <p className="mt-2 text-slate-400">
            Track holdings and get aggregated insights.
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => {
              resetForm();
              setShowForm(true);
            }}
            className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
          >
            Add holding
          </button>
          <button
            onClick={loadInsights}
            disabled={insightsLoading || holdings.length === 0}
            className="rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-900 disabled:opacity-50"
          >
            {insightsLoading ? "Loading..." : "Refresh insights"}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-red-300">
          {error}
        </div>
      )}

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="grid gap-4 rounded-xl border border-slate-800 bg-slate-900/40 p-6 sm:grid-cols-2"
        >
          <h2 className="sm:col-span-2 text-lg font-medium text-white">
            {editingId != null ? "Edit holding" : "Add holding"}
          </h2>
          <input
            required
            disabled={editingId != null}
            placeholder="Ticker"
            value={form.ticker}
            onChange={(e) =>
              setForm({ ...form, ticker: e.target.value.toUpperCase() })
            }
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white disabled:opacity-60"
          />
          <input
            required
            type="number"
            step="any"
            placeholder="Shares"
            value={form.shares}
            onChange={(e) => setForm({ ...form, shares: e.target.value })}
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
          />
          <input
            required
            type="number"
            step="any"
            placeholder="Avg cost"
            value={form.avg_cost}
            onChange={(e) => setForm({ ...form, avg_cost: e.target.value })}
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
          />
          <input
            placeholder="Notes (optional)"
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
          />
          <div className="sm:col-span-2 flex gap-3">
            <button
              type="submit"
              className="flex-1 rounded-lg bg-emerald-600 py-2 font-medium text-white hover:bg-emerald-500"
            >
              Save
            </button>
            <button
              type="button"
              onClick={resetForm}
              className="rounded-lg border border-slate-700 px-4 py-2 text-slate-300 hover:bg-slate-900"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {holdings.length === 0 ? (
        <p className="text-slate-500">No holdings yet. Add your first stock.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-800">
          <table className="w-full text-sm">
            <thead className="bg-slate-900 text-slate-400">
              <tr>
                <th className="px-4 py-3 text-left">Ticker</th>
                <th className="px-4 py-3 text-right">Shares</th>
                <th className="px-4 py-3 text-right">Avg Cost</th>
                <th className="px-4 py-3 text-left">Notes</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((h) => (
                <tr key={h.id} className="border-t border-slate-800">
                  <td className="px-4 py-3">
                    <Link
                      to={`/stock/${h.ticker}`}
                      className="font-medium text-emerald-400 hover:underline"
                    >
                      {h.ticker}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-right font-mono">{h.shares}</td>
                  <td className="px-4 py-3 text-right font-mono">
                    ${h.avg_cost.toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-slate-400">{h.notes ?? "—"}</td>
                  <td className="px-4 py-3 text-right space-x-3">
                    <button
                      onClick={() => startEdit(h)}
                      className="text-slate-400 hover:text-white"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(h.id)}
                      className="text-red-400 hover:text-red-300"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {insights && (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-white">Summary</h2>
              {insights.stale && <StaleBadge />}
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <Stat
                label="Cost basis"
                value={`$${insights.total_cost_basis.toLocaleString()}`}
              />
              <Stat
                label="Market value"
                value={
                  insights.total_market_value != null
                    ? `$${insights.total_market_value.toLocaleString()}`
                    : "—"
                }
              />
              <Stat
                label="Unrealized P&L"
                value={
                  insights.total_unrealized_pnl != null
                    ? `$${insights.total_unrealized_pnl.toLocaleString()} (${insights.total_unrealized_pnl_pct}%)`
                    : "—"
                }
                positive={(insights.total_unrealized_pnl ?? 0) >= 0}
              />
            </div>
            {insights.risk_flags.length > 0 && (
              <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
                <p className="text-sm font-medium text-amber-200">Risk flags</p>
                <ul className="mt-2 list-inside list-disc text-sm text-amber-100/80">
                  {insights.risk_flags.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
            <h2 className="text-lg font-semibold text-white">
              Sector Allocation
            </h2>
            <div className="mt-4">
              <SectorChart allocation={insights.sector_allocation} />
            </div>
          </div>

          <div className="lg:col-span-2 overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-sm">
              <thead className="bg-slate-900 text-slate-400">
                <tr>
                  <th className="px-4 py-3 text-left">Ticker</th>
                  <th className="px-4 py-3 text-right">Price</th>
                  <th className="px-4 py-3 text-right">P&L</th>
                  <th className="px-4 py-3 text-left">Trend</th>
                  <th className="px-4 py-3 text-left">Sentiment</th>
                </tr>
              </thead>
              <tbody>
                {insights.holdings.map((h) => (
                  <tr key={h.ticker} className="border-t border-slate-800">
                    <td className="px-4 py-3">
                      <Link
                        to={`/stock/${h.ticker}`}
                        className="text-emerald-400 hover:underline"
                      >
                        {h.ticker}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {h.current_price != null
                        ? `$${h.current_price.toFixed(2)}`
                        : "—"}
                    </td>
                    <td
                      className={`px-4 py-3 text-right font-mono ${
                        (h.unrealized_pnl ?? 0) >= 0
                          ? "text-emerald-400"
                          : "text-red-400"
                      }`}
                    >
                      {h.unrealized_pnl != null
                        ? `$${h.unrealized_pnl.toFixed(2)} (${h.unrealized_pnl_pct}%)`
                        : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <TrendBadge label={h.trend_label} />
                    </td>
                    <td className="px-4 py-3 capitalize text-slate-400">
                      {h.sentiment_label}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  positive,
}: {
  label: string;
  value: string;
  positive?: boolean;
}) {
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p
        className={`font-mono text-lg ${
          positive === undefined
            ? "text-white"
            : positive
              ? "text-emerald-400"
              : "text-red-400"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
