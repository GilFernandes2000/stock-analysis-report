import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { InsiderBadge, InsiderSignalCard } from "../components/InsiderPanel";
import {
  Badge,
  ErrorNote,
  LoadingSkeleton,
  Panel,
  StaleBadge,
  TrendBadge,
} from "../components/ui";
import { useFavorites } from "../favorites/FavoritesContext";
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
        <Link to="/" className="text-sm text-accent hover:underline">
          ← Back
        </Link>
        <ErrorNote message={error ?? "Stock not found"} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-ink">
              {stock.ticker}
              {stock.company && (
                <span className="ml-3 text-lg font-normal text-ink2">
                  {stock.company}
                </span>
              )}
            </h1>
            <p className="mt-1 text-sm text-muted">
              {[stock.country, stock.sector, stock.industry, stock.exchange]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <FavoriteToggle ticker={stock.ticker} />
            <TrendBadge label={stock.trend.label} />
            {stock.insider_signal &&
              stock.insider_signal.label !== "No activity" && (
                <InsiderBadge signal={stock.insider_signal} />
              )}
            {stock.data_source && (
              <Badge>
                {stock.data_source === "yahoo" ? "Yahoo Finance" : "Finviz"}
              </Badge>
            )}
            {stock.stale && <StaleBadge />}
          </div>
        </div>
        <div className="mt-4 flex items-baseline gap-4">
          {stock.display_price != null && (
            <span className="tnum text-4xl font-bold text-ink">
              {formatMoney(stock.display_price, stock.display_currency ?? currency)}
            </span>
          )}
          {stock.change && (
            <span
              className={`tnum text-lg ${
                stock.change.startsWith("-") ? "text-down" : "text-up"
              }`}
            >
              {stock.change}
            </span>
          )}
        </div>
        {stock.currency_note && (
          <p className="mt-2 text-xs text-muted">{stock.currency_note}</p>
        )}
      </div>

      <div className="flex flex-wrap gap-1 border-b border-grid">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition ${
              tab === t.id
                ? "border-accent text-ink"
                : "border-transparent text-muted hover:text-ink2"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <Metric label="Market cap" value={stock.market_cap} />
          <Metric label="P/E" value={stock.pe} />
          <Metric label="EPS" value={stock.eps} />
          <Metric label="Dividend" value={stock.dividend} />
          <Metric label="Beta" value={stock.beta} />
          <Metric label="52W high" value={stock.high_52w} />
          <Metric label="52W low" value={stock.low_52w} />
          <Metric label="Perf week" value={stock.perf_week} />
          <Metric label="Perf month" value={stock.perf_month} />
          <Metric label="Perf YTD" value={stock.perf_ytd} />
        </div>
      )}

      {tab === "technicals" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Metric label="RSI (14)" value={stock.rsi?.toFixed(2)} />
            <Metric label="vs SMA20" value={formatPct(stock.sma20)} />
            <Metric label="vs SMA50" value={formatPct(stock.sma50)} />
            <Metric label="vs SMA200" value={formatPct(stock.sma200)} />
            <Metric label="Trend score" value={String(stock.trend.score)} />
            <Metric
              label="Analyst upside"
              value={
                stock.analyst_upside_pct != null
                  ? `${stock.analyst_upside_pct > 0 ? "+" : ""}${stock.analyst_upside_pct}%`
                  : undefined
              }
            />
          </div>
          <Panel title="Signals">
            <ul className="space-y-1.5 text-sm text-ink2">
              {stock.trend.signals.map((s) => (
                <li key={s} className="flex items-start gap-2">
                  <span className="text-accent">▸</span>
                  {s}
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      )}

      {tab === "ownership" && (
        <div className="space-y-4">
          {stock.insider_signal && (
            <InsiderSignalCard signal={stock.insider_signal} />
          )}
          <div className="grid grid-cols-3 gap-3">
            <Metric label="Institutional own" value={stock.inst_own} />
            <Metric label="Insider own" value={stock.insider_own} />
            <Metric label="Short float" value={stock.short_float} />
          </div>
          {stock.insider_trades.length > 0 && (
            <div className="overflow-x-auto rounded-2xl border border-grid">
              <table className="w-full text-sm">
                <thead className="bg-panel text-left text-[11px] uppercase tracking-wider text-muted">
                  <tr>
                    <th className="px-4 py-3">Insider</th>
                    <th className="px-4 py-3">Transaction</th>
                    <th className="px-4 py-3 text-right">Shares</th>
                    <th className="px-4 py-3 text-right">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {stock.insider_trades.map((t, i) => (
                    <tr key={i} className="border-t border-grid">
                      <td className="px-4 py-2.5 text-ink2">{t.insider}</td>
                      <td className="px-4 py-2.5 text-ink2">{t.transaction}</td>
                      <td className="tnum px-4 py-2.5 text-right text-ink2">
                        {t.shares}
                      </td>
                      <td className="tnum px-4 py-2.5 text-right text-muted">
                        {t.date}
                      </td>
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
          <Panel title="Overall sentiment">
            <p className="text-lg font-semibold capitalize text-ink">
              {stock.sentiment.label}
            </p>
            <p className="mt-1 text-sm text-muted">
              {stock.sentiment.positive_count} positive ·{" "}
              {stock.sentiment.neutral_count} neutral ·{" "}
              {stock.sentiment.negative_count} negative
            </p>
          </Panel>
          <div className="space-y-2">
            {stock.sentiment.headlines.map((item, i) => (
              <div key={i} className="rounded-2xl border border-grid bg-panel p-4">
                {item.url ? (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm font-medium text-ink hover:text-accent"
                  >
                    {item.title}
                  </a>
                ) : (
                  <p className="text-sm font-medium text-ink">{item.title}</p>
                )}
                <div className="mt-1.5 flex gap-3 text-xs text-muted">
                  {item.date && <span>{item.date}</span>}
                  {item.sentiment && (
                    <span className="capitalize">{item.sentiment}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
          {stock.analyst_targets.length > 0 && (
            <Panel title="Analyst targets">
              <ul className="space-y-1.5 text-sm text-ink2">
                {stock.analyst_targets.map((t, i) => (
                  <li key={i}>
                    {t.analyst}:{" "}
                    {t.price_target != null
                      ? formatMoney(
                          t.price_target,
                          stock.display_currency ?? currency
                        )
                      : "—"}{" "}
                    <span className="text-muted">({t.date})</span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
        </div>
      )}

      {tab === "chart" && stock.chart_url && (
        <Panel title="Chart">
          {stock.data_source === "yahoo" ? (
            <div className="space-y-3">
              <p className="text-sm text-muted">
                Interactive chart hosted on Yahoo Finance.
              </p>
              <a
                href={stock.chart_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent-soft"
              >
                Open {stock.ticker} chart on Yahoo Finance
              </a>
            </div>
          ) : (
            <div className="overflow-hidden rounded-xl bg-white">
              <img
                src={stock.chart_url}
                alt={`${stock.ticker} chart`}
                className="w-full"
              />
            </div>
          )}
        </Panel>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="rounded-2xl border border-grid bg-panel px-4 py-3">
      <p className="text-[11px] font-medium uppercase tracking-wider text-muted">
        {label}
      </p>
      <p className="tnum mt-1 text-lg font-semibold text-ink">{value ?? "—"}</p>
    </div>
  );
}

function formatPct(value?: number | null) {
  if (value == null) return undefined;
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function FavoriteToggle({ ticker }: { ticker: string }) {
  const { isFavorite, toggle } = useFavorites();
  const active = isFavorite(ticker);
  return (
    <button
      onClick={() => toggle(ticker)}
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-0.5 text-xs font-medium transition ${
        active
          ? "border-warn/40 bg-warn/10 text-warn"
          : "border-edge text-ink2 hover:border-warn/40 hover:text-warn"
      }`}
      title={active ? "Remove from favorites" : "Add to favorites"}
    >
      <span className="text-sm leading-none">{active ? "★" : "☆"}</span>
      {active ? "Following" : "Follow"}
    </button>
  );
}
