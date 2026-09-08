import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { InsiderBadge } from "../components/InsiderPanel";
import {
  AllocationDonut,
  ContributorsBar,
  TwrChart,
  ValueChart,
} from "../components/charts";
import {
  Badge,
  Button,
  DeltaText,
  EmptyState,
  ErrorNote,
  LoadingSkeleton,
  Panel,
  Spinner,
  StaleBadge,
  StatCard,
} from "../components/ui";
import { usePageTitle } from "../hooks/usePageTitle";
import type {
  PortfolioAnalytics,
  PortfolioInsiderResponse,
  Transaction,
} from "../types";
import { formatMoney } from "../utils/currency";
import { AddTransactionModal } from "./portfolio/AddTransactionModal";
import { ImportWizard } from "./portfolio/ImportWizard";

type Tab = "overview" | "holdings" | "transactions";

export function PortfolioDetail() {
  const { id = "" } = useParams();
  const portfolioId = Number(id);
  const navigate = useNavigate();
  const [analytics, setAnalytics] = useState<PortfolioAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [showImport, setShowImport] = useState(false);
  const [showAddTxn, setShowAddTxn] = useState(false);
  const [reportBusy, setReportBusy] = useState(false);

  usePageTitle(analytics?.name ?? "Portfolio");

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .portfolioAnalytics(portfolioId)
      .then(setAnalytics)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [portfolioId]);

  useEffect(() => {
    if (portfolioId) load();
  }, [portfolioId, load]);

  async function handleGenerateReport() {
    setReportBusy(true);
    try {
      const report = await api.generateTearsheet([portfolioId]);
      navigate(`/reports/${report.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Report generation failed");
    } finally {
      setReportBusy(false);
    }
  }

  async function handleDelete() {
    if (!analytics) return;
    if (!window.confirm(`Delete portfolio "${analytics.name}" and all its transactions?`))
      return;
    await api.deletePortfolio(portfolioId);
    navigate("/");
  }

  if (loading && !analytics) return <LoadingSkeleton rows={5} />;

  if (error && !analytics) {
    return (
      <div className="space-y-4">
        <Link to="/" className="text-sm text-accent hover:underline">
          ← Portfolios
        </Link>
        <ErrorNote message={error} />
      </div>
    );
  }
  if (!analytics) return null;

  const a = analytics;
  const ccy = a.base_currency;
  const hasData = a.positions.length > 0 || a.closed_positions.length > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link to="/" className="text-xs text-muted hover:text-accent">
            ← Portfolios
          </Link>
          <div className="mt-1 flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-ink">{a.name}</h1>
            {a.stale && <StaleBadge />}
            {loading && <Spinner />}
          </div>
          <p className="mt-0.5 text-xs text-muted">
            Base {ccy} · benchmark {a.benchmark} · as of{" "}
            {new Date(a.as_of).toLocaleString()}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" onClick={() => setShowAddTxn(true)}>
            Add transaction
          </Button>
          <Button variant="ghost" onClick={() => setShowImport(true)}>
            Import CSV
          </Button>
          <Button onClick={handleGenerateReport} disabled={reportBusy || !hasData}>
            {reportBusy ? "Building report…" : "Generate report"}
          </Button>
        </div>
      </div>

      {error && <ErrorNote message={error} />}

      {!hasData ? (
        <EmptyState
          title="No transactions yet"
          hint="Import your Degiro Transactions.csv / Account.csv or your Trading 212 history export — or add transactions manually."
          action={<Button onClick={() => setShowImport(true)}>Import broker CSV</Button>}
        />
      ) : (
        <>
          {/* Headline stats */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              label="Market value"
              value={formatMoney(a.market_value, ccy)}
              sub={
                a.cash_balance > 0 ? (
                  <>+ {formatMoney(a.cash_balance, ccy)} cash</>
                ) : undefined
              }
            />
            <StatCard
              label="Total return"
              value={
                <>
                  {a.total_return >= 0 ? "+" : ""}
                  {formatMoney(a.total_return, ccy)}
                </>
              }
              tone={a.total_return >= 0 ? "up" : "down"}
              sub={<DeltaText value={a.total_return_pct} />}
            />
            <StatCard
              label="Unrealized P&L"
              value={
                <>
                  {a.unrealized_pnl >= 0 ? "+" : ""}
                  {formatMoney(a.unrealized_pnl, ccy)}
                </>
              }
              tone={a.unrealized_pnl >= 0 ? "up" : "down"}
              sub={<DeltaText value={a.unrealized_pnl_pct} />}
            />
            <StatCard
              label="Day change"
              value={
                a.day_change != null ? (
                  <>
                    {a.day_change >= 0 ? "+" : ""}
                    {formatMoney(a.day_change, ccy)}
                  </>
                ) : (
                  "—"
                )
              }
              tone={
                a.day_change == null ? "neutral" : a.day_change >= 0 ? "up" : "down"
              }
              sub={<DeltaText value={a.day_change_pct} />}
            />
          </div>

          {/* Tabs */}
          <div className="flex gap-1 border-b border-grid">
            {(
              [
                ["overview", "Overview"],
                ["holdings", `Holdings (${a.positions.length})`],
                ["transactions", "Transactions"],
              ] as [Tab, string][]
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition ${
                  tab === key
                    ? "border-accent text-ink"
                    : "border-transparent text-muted hover:text-ink2"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {tab === "overview" && <OverviewTab analytics={a} />}
          {tab === "holdings" && <HoldingsTab analytics={a} />}
          {tab === "transactions" && (
            <TransactionsTab portfolioId={portfolioId} onChanged={load} />
          )}
        </>
      )}

      {/* Danger zone */}
      <div className="flex justify-end pt-4">
        <button
          onClick={handleDelete}
          className="text-xs text-muted transition hover:text-down"
        >
          Delete portfolio
        </button>
      </div>

      {showImport && (
        <ImportWizard
          portfolioId={portfolioId}
          onClose={() => setShowImport(false)}
          onImported={() => {
            setShowImport(false);
            load();
          }}
        />
      )}
      {showAddTxn && (
        <AddTransactionModal
          portfolioId={portfolioId}
          baseCurrency={ccy}
          onClose={() => setShowAddTxn(false)}
          onAdded={() => {
            setShowAddTxn(false);
            load();
          }}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Overview tab
// ---------------------------------------------------------------------------

function OverviewTab({ analytics: a }: { analytics: PortfolioAnalytics }) {
  const ccy = a.base_currency;
  const [perfMode, setPerfMode] = useState<"value" | "twr">("value");
  return (
    <div className="space-y-4">
      <Panel
        title="Performance"
        action={
          <div className="flex gap-1 rounded-lg bg-inset p-0.5">
            {(
              [
                ["value", "Value"],
                ["twr", "vs Benchmark"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setPerfMode(key)}
                className={`rounded-md px-3 py-1 text-xs font-medium transition ${
                  perfMode === key ? "bg-raised text-ink" : "text-muted hover:text-ink2"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        }
      >
        {perfMode === "value" ? (
          <ValueChart data={a.performance} currency={ccy} />
        ) : (
          <TwrChart data={a.performance} benchmarkLabel={a.benchmark} />
        )}
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Risk metrics">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
            <RiskStat label="Time-weighted return" value={a.risk.twr_pct} suffix="%" signed />
            <RiskStat
              label={`Benchmark (${a.benchmark})`}
              value={a.risk.benchmark_return_pct}
              suffix="%"
              signed
            />
            <RiskStat label="Volatility (ann.)" value={a.risk.volatility_pct} suffix="%" />
            <RiskStat label="Sharpe ratio" value={a.risk.sharpe} />
            <RiskStat label="Max drawdown" value={a.risk.max_drawdown_pct} suffix="%" signed />
            <RiskStat label="Beta" value={a.risk.beta} />
          </dl>
        </Panel>
        <Panel title="Income & costs">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
            <MoneyStat label="Dividends" value={a.dividends_received} ccy={ccy} tone="up" />
            <MoneyStat label="Interest" value={a.cash_flows.interest} ccy={ccy} />
            <MoneyStat label="Realized P&L" value={a.realized_pnl} ccy={ccy} signedTone />
            <MoneyStat label="Fees paid" value={-a.fees_paid} ccy={ccy} tone="down" />
            <MoneyStat label="Taxes" value={-a.cash_flows.taxes} ccy={ccy} tone="down" />
            <MoneyStat label="Net deposits" value={a.cash_flows.deposits - a.cash_flows.withdrawals} ccy={ccy} />
          </dl>
        </Panel>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Sector allocation">
          <AllocationDonut data={a.sector_allocation} currency={ccy} />
        </Panel>
        <Panel title="Currency exposure">
          <AllocationDonut data={a.currency_allocation} currency={ccy} />
        </Panel>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Top contributors & detractors">
          <ContributorsBar
            contributors={a.top_contributors}
            detractors={a.top_detractors}
            currency={ccy}
          />
        </Panel>
        <Panel title="Risk flags">
          {a.risk_flags.length === 0 ? (
            <p className="text-sm text-muted">No structural risk flags detected.</p>
          ) : (
            <ul className="space-y-2">
              {a.risk_flags.map((flag) => (
                <li key={flag} className="flex items-start gap-2 text-sm text-ink2">
                  <span className="mt-0.5 text-warn">⚠</span>
                  {flag}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <InsiderActivityPanel portfolioId={a.portfolio_id} />
    </div>
  );
}

function InsiderActivityPanel({ portfolioId }: { portfolioId: number }) {
  const [data, setData] = useState<PortfolioInsiderResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .portfolioInsider(portfolioId)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((e) => {
        if (!cancelled)
          setError(e instanceof Error ? e.message : "Failed to load insider data");
      });
    return () => {
      cancelled = true;
    };
  }, [portfolioId]);

  return (
    <Panel
      title="Insider activity"
      action={
        !data && !error ? <Spinner label="Scanning insider filings…" /> : undefined
      }
    >
      {error ? (
        <p className="text-sm text-muted">{error}</p>
      ) : !data ? (
        <p className="text-sm text-muted">
          Checking recent insider buys and sells across your holdings…
        </p>
      ) : (
        <div className="space-y-4">
          <ul className="space-y-2">
            {data.advice.map((item) => (
              <li key={item} className="flex items-start gap-2 text-sm text-ink2">
                <span className="mt-0.5 text-accent">▸</span>
                {item}
              </li>
            ))}
          </ul>
          <div className="overflow-x-auto border-t border-grid pt-3">
            <table className="w-full min-w-[560px] text-sm">
              <thead className="text-left text-[11px] uppercase tracking-wider text-muted">
                <tr>
                  <th className="px-3 py-2">Holding</th>
                  <th className="px-3 py-2">Signal</th>
                  <th className="px-3 py-2 text-right">Buys / Sales (6m)</th>
                  <th className="px-3 py-2 text-right">Net flow</th>
                </tr>
              </thead>
              <tbody>
                {data.holdings.map((h) => (
                  <tr key={h.ticker} className="border-t border-grid/60">
                    <td className="px-3 py-2">
                      <Link
                        to={`/stock/${h.ticker}`}
                        className="font-medium text-ink hover:text-accent"
                      >
                        {h.ticker}
                      </Link>
                    </td>
                    <td className="px-3 py-2">
                      <InsiderBadge signal={h.signal} />
                    </td>
                    <td className="tnum px-3 py-2 text-right text-ink2">
                      {h.signal.buy_count} / {h.signal.sell_count}
                    </td>
                    <td
                      className={`tnum px-3 py-2 text-right ${
                        h.signal.net_value > 0
                          ? "text-up"
                          : h.signal.net_value < 0
                            ? "text-down"
                            : "text-muted"
                      }`}
                    >
                      {h.signal.net_value === 0
                        ? "—"
                        : `${h.signal.net_value > 0 ? "+" : "-"}$${Math.abs(
                            h.signal.net_value
                          ).toLocaleString(undefined, {
                            maximumFractionDigits: 0,
                          })}`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[11px] text-muted">
            Open-market transactions reported in SEC filings (via Finviz; Yahoo
            Finance where available). Insider buys are historically a stronger
            signal than sales.
          </p>
        </div>
      )}
    </Panel>
  );
}

function RiskStat({
  label,
  value,
  suffix = "",
  signed = false,
}: {
  label: string;
  value?: number | null;
  suffix?: string;
  signed?: boolean;
}) {
  return (
    <div>
      <dt className="text-[11px] font-medium uppercase tracking-wider text-muted">
        {label}
      </dt>
      <dd
        className={`tnum mt-0.5 text-lg font-semibold ${
          value == null
            ? "text-muted"
            : signed && value > 0
              ? "text-up"
              : signed && value < 0
                ? "text-down"
                : "text-ink"
        }`}
      >
        {value == null ? "—" : `${signed && value > 0 ? "+" : ""}${value}${suffix}`}
      </dd>
    </div>
  );
}

function MoneyStat({
  label,
  value,
  ccy,
  tone,
  signedTone = false,
}: {
  label: string;
  value: number;
  ccy: string;
  tone?: "up" | "down";
  signedTone?: boolean;
}) {
  const color = signedTone
    ? value > 0
      ? "text-up"
      : value < 0
        ? "text-down"
        : "text-ink"
    : tone === "up" && value > 0
      ? "text-up"
      : tone === "down" && value < 0
        ? "text-down"
        : "text-ink";
  return (
    <div>
      <dt className="text-[11px] font-medium uppercase tracking-wider text-muted">
        {label}
      </dt>
      <dd className={`tnum mt-0.5 text-lg font-semibold ${color}`}>
        {value > 0 ? "+" : ""}
        {formatMoney(value, ccy)}
      </dd>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Holdings tab
// ---------------------------------------------------------------------------

function HoldingsTab({ analytics: a }: { analytics: PortfolioAnalytics }) {
  const ccy = a.base_currency;
  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-2xl border border-grid">
        <table className="w-full min-w-[900px] text-sm">
          <thead className="bg-panel text-left text-[11px] uppercase tracking-wider text-muted">
            <tr>
              <th className="px-4 py-3">Instrument</th>
              <th className="px-4 py-3 text-right">Shares</th>
              <th className="px-4 py-3 text-right">Avg cost</th>
              <th className="px-4 py-3 text-right">Price</th>
              <th className="px-4 py-3 text-right">Value</th>
              <th className="px-4 py-3 text-right">Weight</th>
              <th className="px-4 py-3 text-right">Day</th>
              <th className="px-4 py-3 text-right">Unrealized P&L</th>
              <th className="px-4 py-3 text-right">Dividends</th>
            </tr>
          </thead>
          <tbody>
            {a.positions.map((p) => (
              <tr
                key={p.ticker}
                className="border-t border-grid transition hover:bg-panel/60"
              >
                <td className="px-4 py-3">
                  <Link to={`/stock/${p.ticker}`} className="group block">
                    <span className="font-semibold text-ink group-hover:text-accent">
                      {p.ticker}
                    </span>
                    {p.name && (
                      <span className="block max-w-[220px] truncate text-xs text-muted">
                        {p.name}
                      </span>
                    )}
                  </Link>
                </td>
                <td className="tnum px-4 py-3 text-right text-ink2">{p.shares}</td>
                <td className="tnum px-4 py-3 text-right text-ink2">
                  {formatMoney(p.avg_cost, ccy)}
                  {p.native_avg_cost_currency &&
                    p.native_avg_cost_currency !== ccy &&
                    p.native_avg_cost != null && (
                      <span className="block text-[11px] text-muted">
                        {formatMoney(p.native_avg_cost, p.native_avg_cost_currency)}
                      </span>
                    )}
                </td>
                <td className="tnum px-4 py-3 text-right text-ink">
                  {p.current_price != null ? formatMoney(p.current_price, ccy) : "—"}
                  {p.native_currency && p.native_currency !== ccy && p.native_price != null && (
                    <span className="block text-[11px] text-muted">
                      {formatMoney(p.native_price, p.native_currency)}
                    </span>
                  )}
                </td>
                <td className="tnum px-4 py-3 text-right font-medium text-ink">
                  {p.market_value != null ? formatMoney(p.market_value, ccy) : "—"}
                </td>
                <td className="tnum px-4 py-3 text-right text-ink2">
                  {p.weight_pct != null ? `${p.weight_pct.toFixed(1)}%` : "—"}
                </td>
                <td className="px-4 py-3 text-right">
                  <DeltaText value={p.day_change_pct} />
                </td>
                <td className="px-4 py-3 text-right">
                  {p.unrealized_pnl != null ? (
                    <>
                      <span
                        className={`tnum ${p.unrealized_pnl >= 0 ? "text-up" : "text-down"}`}
                      >
                        {p.unrealized_pnl >= 0 ? "+" : ""}
                        {formatMoney(p.unrealized_pnl, ccy)}
                      </span>
                      <DeltaText
                        value={p.unrealized_pnl_pct}
                        className="block text-[11px]"
                      />
                    </>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="tnum px-4 py-3 text-right text-ink2">
                  {p.dividends ? formatMoney(p.dividends, ccy) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {a.closed_positions.length > 0 && (
        <Panel title="Closed positions">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[480px] text-sm">
              <thead className="text-left text-[11px] uppercase tracking-wider text-muted">
                <tr>
                  <th className="px-3 py-2">Instrument</th>
                  <th className="px-3 py-2 text-right">Realized P&L</th>
                  <th className="px-3 py-2 text-right">Dividends</th>
                  <th className="px-3 py-2 text-right">Fees</th>
                </tr>
              </thead>
              <tbody>
                {a.closed_positions.map((p) => (
                  <tr key={p.ticker} className="border-t border-grid">
                    <td className="px-3 py-2">
                      <span className="font-medium text-ink">{p.ticker}</span>
                      {p.name && (
                        <span className="ml-2 text-xs text-muted">{p.name}</span>
                      )}
                    </td>
                    <td
                      className={`tnum px-3 py-2 text-right ${
                        p.realized_pnl >= 0 ? "text-up" : "text-down"
                      }`}
                    >
                      {p.realized_pnl >= 0 ? "+" : ""}
                      {formatMoney(p.realized_pnl, a.base_currency)}
                    </td>
                    <td className="tnum px-3 py-2 text-right text-ink2">
                      {p.dividends ? formatMoney(p.dividends, a.base_currency) : "—"}
                    </td>
                    <td className="tnum px-3 py-2 text-right text-ink2">
                      {p.fees ? formatMoney(p.fees, a.base_currency) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Transactions tab
// ---------------------------------------------------------------------------

const TXN_TONE: Record<string, "up" | "down" | "neutral" | "accent" | "warn"> = {
  buy: "accent",
  sell: "warn",
  dividend: "up",
  deposit: "neutral",
  withdrawal: "neutral",
  fee: "down",
  tax: "down",
  interest: "up",
  other: "neutral",
};

function TransactionsTab({
  portfolioId,
  onChanged,
}: {
  portfolioId: number;
  onChanged: () => void;
}) {
  const [txns, setTxns] = useState<Transaction[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("all");

  const load = useCallback(() => {
    api
      .listTransactions(portfolioId)
      .then(setTxns)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, [portfolioId]);

  useEffect(load, [load]);

  const filtered = useMemo(
    () => (txns ?? []).filter((t) => filter === "all" || t.type === filter),
    [txns, filter]
  );

  async function handleDelete(txnId: number) {
    if (!window.confirm("Delete this transaction?")) return;
    await api.deleteTransaction(portfolioId, txnId);
    load();
    onChanged();
  }

  if (error) return <ErrorNote message={error} />;
  if (txns === null) return <LoadingSkeleton rows={4} />;

  const types = ["all", ...new Set(txns.map((t) => t.type))];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {types.map((t) => (
          <button
            key={t}
            onClick={() => setFilter(t)}
            className={`rounded-full border px-3 py-1 text-xs font-medium capitalize transition ${
              filter === t
                ? "border-accent/60 bg-accent/10 text-accent"
                : "border-edge text-muted hover:text-ink2"
            }`}
          >
            {t}
          </button>
        ))}
        <span className="ml-auto self-center text-xs text-muted">
          {filtered.length} of {txns.length}
        </span>
      </div>
      <div className="overflow-x-auto rounded-2xl border border-grid">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="bg-panel text-left text-[11px] uppercase tracking-wider text-muted">
            <tr>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Instrument</th>
              <th className="px-4 py-3 text-right">Shares</th>
              <th className="px-4 py-3 text-right">Price</th>
              <th className="px-4 py-3 text-right">Amount</th>
              <th className="px-4 py-3 text-right">Fees</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((t) => (
              <tr key={t.id} className="border-t border-grid hover:bg-panel/60">
                <td className="tnum whitespace-nowrap px-4 py-2.5 text-ink2">
                  {new Date(t.date).toLocaleDateString()}
                </td>
                <td className="px-4 py-2.5">
                  <Badge tone={TXN_TONE[t.type] ?? "neutral"}>{t.type}</Badge>
                </td>
                <td className="px-4 py-2.5">
                  {t.ticker ? (
                    <Link
                      to={`/stock/${t.ticker}`}
                      className="font-medium text-ink hover:text-accent"
                    >
                      {t.ticker}
                    </Link>
                  ) : (
                    <span className="text-muted">{t.note ?? "—"}</span>
                  )}
                </td>
                <td className="tnum px-4 py-2.5 text-right text-ink2">
                  {t.shares ?? "—"}
                </td>
                <td className="tnum px-4 py-2.5 text-right text-ink2">
                  {t.price != null
                    ? formatMoney(t.price, t.currency ?? undefined)
                    : "—"}
                </td>
                <td
                  className={`tnum px-4 py-2.5 text-right ${
                    t.amount > 0 ? "text-up" : t.amount < 0 ? "text-ink" : "text-muted"
                  }`}
                >
                  {t.amount > 0 ? "+" : ""}
                  {formatMoney(t.amount)}
                </td>
                <td className="tnum px-4 py-2.5 text-right text-ink2">
                  {t.fees ? formatMoney(t.fees) : "—"}
                </td>
                <td className="px-2 py-2.5 text-right">
                  <button
                    onClick={() => handleDelete(t.id)}
                    className="rounded px-2 py-0.5 text-xs text-muted transition hover:text-down"
                    title="Delete transaction"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

