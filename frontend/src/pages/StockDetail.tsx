import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { StaleBadge } from "../components/StaleBadge";
import { TrendBadge } from "../components/TrendBadge";
import { useDisplayCurrency } from "../hooks/useDisplayCurrency";
import { usePageTitle } from "../hooks/usePageTitle";
import type { StockAnalysis } from "../types";
import { formatMoney } from "../utils/currency";

type Tab = "overview" | "technicals" | "ownership" | "news" | "chart";

export function StockDetail() {
  const { ticker = "" } = useParams();
  usePageTitle(ticker);
  const { currency } = useDisplayCurrency();
  const [stock, setStock] = useState<StockAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    setError(null);
    api
      .getStock(ticker)
      .then(setStock)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [ticker, currency]);

  const tabs: { id: Tab; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "technicals", label: "Technicals" },
    { id: "ownership", label: "Ownership" },
    { id: "news", label: "News & Sentiment" },
    { id: "chart", label: "Chart" },
  ];

  if (loading) return <LoadingSkeleton rows={6} />;

  if (error || !stock) {
    return (
      <div className="space-y-4">
        <Link to="/" className="text-sm text-emerald-400 hover:underline">
          ← Back to dashboard
        </Link>
        <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-6 text-red-300">
          {error ?? "Stock not found"}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link to="/" className="text-sm text-emerald-400 hover:underline">
          ← Back to dashboard
        </Link>
        <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-white">
              {stock.ticker}
              {stock.company && (
                <span className="ml-3 text-xl font-normal text-slate-400">
                  {stock.company}
                </span>
              )}
            </h1>
            <p className="mt-1 text-slate-400">
              {[stock.country, stock.sector, stock.industry, stock.exchange]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <TrendBadge label={stock.trend.label} />
            {stock.data_source && (
              <span className="rounded-full border border-slate-600 bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                {stock.data_source === "yahoo" ? "Yahoo Finance" : "Finviz"}
              </span>
            )}
            {stock.stale && <StaleBadge />}
          </div>
        </div>
        <div className="mt-4 flex items-baseline gap-4">
          {stock.display_price != null && (
            <span className="text-4xl font-mono font-bold text-white">
              {formatMoney(stock.display_price, stock.display_currency ?? currency)}
            </span>
          )}
          {stock.change && (
            <span
              className={`text-lg ${
                stock.change.startsWith("-")
                  ? "text-red-400"
                  : "text-emerald-400"
              }`}
            >
              {stock.change}
            </span>
          )}
        </div>
        {stock.currency_note && (
          <p className="mt-2 text-sm text-slate-500">{stock.currency_note}</p>
        )}
      </div>

      <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-2">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
              tab === t.id
                ? "bg-slate-800 text-white"
                : "text-slate-400 hover:text-white"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Metric label="Market Cap" value={stock.market_cap} />
          <Metric label="P/E" value={stock.pe} />
          <Metric label="EPS" value={stock.eps} />
          <Metric label="Dividend" value={stock.dividend} />
          <Metric label="Beta" value={stock.beta} />
          <Metric label="52W High" value={stock.high_52w} />
          <Metric label="52W Low" value={stock.low_52w} />
          <Metric label="Perf Week" value={stock.perf_week} />
          <Metric label="Perf YTD" value={stock.perf_ytd} />
        </div>
      )}

      {tab === "technicals" && (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="RSI (14)" value={stock.rsi?.toFixed(2)} />
            <Metric label="SMA20 dist" value={formatPct(stock.sma20)} />
            <Metric label="SMA50 dist" value={formatPct(stock.sma50)} />
            <Metric label="SMA200 dist" value={formatPct(stock.sma200)} />
            <Metric label="Trend Score" value={String(stock.trend.score)} />
            <Metric
              label="Analyst Upside"
              value={
                stock.analyst_upside_pct != null
                  ? `${stock.analyst_upside_pct > 0 ? "+" : ""}${stock.analyst_upside_pct}%`
                  : undefined
              }
            />
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
            <h3 className="mb-2 font-medium text-white">Signals</h3>
            <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
              {stock.trend.signals.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {tab === "ownership" && (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <Metric label="Institutional Own" value={stock.inst_own} />
            <Metric label="Insider Own" value={stock.insider_own} />
            <Metric label="Short Float" value={stock.short_float} />
          </div>
          {stock.insider_trades.length > 0 && (
            <div className="overflow-x-auto rounded-xl border border-slate-800">
              <table className="w-full text-sm">
                <thead className="bg-slate-900 text-slate-400">
                  <tr>
                    <th className="px-4 py-2 text-left">Insider</th>
                    <th className="px-4 py-2 text-left">Transaction</th>
                    <th className="px-4 py-2 text-left">Shares</th>
                    <th className="px-4 py-2 text-left">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {stock.insider_trades.map((t, i) => (
                    <tr key={i} className="border-t border-slate-800">
                      <td className="px-4 py-2">{t.insider}</td>
                      <td className="px-4 py-2">{t.transaction}</td>
                      <td className="px-4 py-2">{t.shares}</td>
                      <td className="px-4 py-2">{t.date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === "news" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
            <p className="text-sm text-slate-400">Overall sentiment</p>
            <p className="text-lg font-medium capitalize text-white">
              {stock.sentiment.label}
            </p>
            <p className="text-sm text-slate-500">
              {stock.sentiment.positive_count} positive ·{" "}
              {stock.sentiment.neutral_count} neutral ·{" "}
              {stock.sentiment.negative_count} negative
            </p>
          </div>
          <div className="space-y-3">
            {stock.sentiment.headlines.map((item, i) => (
              <div
                key={i}
                className="rounded-xl border border-slate-800 bg-slate-900/40 p-4"
              >
                {item.url ? (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noreferrer"
                    className="font-medium text-white hover:text-emerald-400"
                  >
                    {item.title}
                  </a>
                ) : (
                  <p className="font-medium text-white">{item.title}</p>
                )}
                <div className="mt-2 flex gap-3 text-xs text-slate-500">
                  {item.date && <span>{item.date}</span>}
                  {item.sentiment && (
                    <span className="capitalize">{item.sentiment}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
          {stock.analyst_targets.length > 0 && (
            <div className="rounded-xl border border-slate-800 p-4">
              <h3 className="mb-3 font-medium text-white">Analyst Targets</h3>
              <ul className="space-y-2 text-sm text-slate-300">
                {stock.analyst_targets.map((t, i) => (
                  <li key={i}>
                    {t.analyst}:{" "}
                    {t.price_target != null
                      ? formatMoney(t.price_target, stock.display_currency ?? currency)
                      : "—"}{" "}
                    ({t.date})
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {tab === "chart" && stock.chart_url && (
        <div className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          {stock.data_source === "yahoo" ? (
            <>
              <p className="text-sm text-slate-400">
                Interactive chart hosted on Yahoo Finance.
              </p>
              <a
                href={stock.chart_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
              >
                Open {stock.ticker} chart on Yahoo Finance
              </a>
            </>
          ) : (
            <div className="overflow-hidden rounded-xl bg-white">
              <img
                src={stock.chart_url}
                alt={`${stock.ticker} chart`}
                className="w-full"
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 font-mono text-lg text-white">{value ?? "—"}</p>
    </div>
  );
}

function formatPct(value?: number | null) {
  if (value == null) return undefined;
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}
