import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import {
  AllocationDonut,
  ContributorsBar,
  TwrChart,
  ValueChart,
} from "../components/charts";
import {
  Badge,
  Button,
  ErrorNote,
  LoadingSkeleton,
  TrendBadge,
} from "../components/ui";
import { usePageTitle } from "../hooks/usePageTitle";
import type {
  MarketReportContent,
  ReportDetail,
  TearsheetContent,
  TearsheetSection,
} from "../types";
import { formatMoney } from "../utils/currency";

export function ReportView() {
  const { id = "" } = useParams();
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  usePageTitle(report?.title ?? "Report");

  useEffect(() => {
    api
      .getReport(Number(id))
      .then(setReport)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, [id]);

  if (error) {
    return (
      <div className="space-y-4">
        <Link to="/reports" className="text-sm text-accent hover:underline">
          ← Reports
        </Link>
        <ErrorNote message={error} />
      </div>
    );
  }
  if (!report) return <LoadingSkeleton rows={6} />;

  const isTearsheet = report.kind === "portfolio";

  return (
    <div className="print-sheet space-y-6">
      <div className="no-print flex flex-wrap items-center justify-between gap-3">
        <Link to="/reports" className="text-sm text-muted hover:text-accent">
          ← Reports
        </Link>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => window.print()}>
            Export PDF
          </Button>
        </div>
      </div>

      {isTearsheet ? (
        <Tearsheet content={report.content_json as TearsheetContent} />
      ) : (
        <MarketReport
          report={report}
          content={report.content_json as MarketReportContent}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tearsheet
// ---------------------------------------------------------------------------

function Tearsheet({ content }: { content: TearsheetContent }) {
  const generated = new Date(content.generated_at);
  return (
    <article className="space-y-8">
      {/* Letterhead */}
      <header className="sheet-panel rounded-2xl border border-grid bg-panel p-6 sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-lg font-bold text-white">
              M
            </span>
            <div>
              <p className="ink text-sm font-bold tracking-tight text-ink">Meridian</p>
              <p className="mut text-[10px] uppercase tracking-widest text-muted">
                Portfolio Intelligence
              </p>
            </div>
          </div>
          <div className="text-right">
            <p className="mut text-[10px] uppercase tracking-widest text-muted">
              Confidential — prepared for internal use
            </p>
            <p className="ink2 mt-1 text-xs text-ink2">
              {generated.toLocaleDateString(undefined, {
                weekday: "long",
                day: "numeric",
                month: "long",
                year: "numeric",
              })}
            </p>
          </div>
        </div>
        <h1 className="ink mt-6 text-2xl font-bold tracking-tight text-ink sm:text-3xl">
          Portfolio Tearsheet
        </h1>
        <p className="ink2 mt-1 text-sm text-ink2">
          {content.sections.map((s) => s.portfolio.name).join(" · ")}
        </p>

        {content.combined && (
          <div className="mt-6 grid grid-cols-2 gap-4 border-t border-grid pt-5 sm:grid-cols-4">
            <LetterheadStat
              label="Combined market value"
              value={formatMoney(
                content.combined.market_value,
                content.combined.base_currency
              )}
              note={content.combined.mixed_currencies ? "mixed currencies" : undefined}
            />
            <LetterheadStat
              label="Combined total return"
              value={formatMoney(
                content.combined.total_return,
                content.combined.base_currency
              )}
              tone={content.combined.total_return >= 0 ? "up" : "down"}
            />
            <LetterheadStat
              label="Dividend income"
              value={formatMoney(
                content.combined.dividends_received,
                content.combined.base_currency
              )}
            />
            <LetterheadStat
              label="Fees paid"
              value={formatMoney(
                content.combined.fees_paid,
                content.combined.base_currency
              )}
            />
          </div>
        )}
      </header>

      {content.sections.map((section, i) => (
        <TearsheetPortfolioSection
          key={section.portfolio.portfolio_id}
          section={section}
          pageBreak={i > 0}
        />
      ))}

      <footer className="mut px-2 pb-4 text-center text-[10px] leading-relaxed text-muted">
        Market data from Finviz and Yahoo Finance, delayed 15–20 minutes. Performance
        figures use the average-cost method and time-weighted returns. This document
        is generated automatically for personal use and does not constitute
        investment advice.
      </footer>
    </article>
  );
}

function LetterheadStat({
  label,
  value,
  note,
  tone,
}: {
  label: string;
  value: string;
  note?: string;
  tone?: "up" | "down";
}) {
  return (
    <div>
      <p className="mut text-[10px] font-medium uppercase tracking-widest text-muted">
        {label}
      </p>
      <p
        className={`tnum mt-1 text-lg font-semibold ${
          tone === "up" ? "text-up" : tone === "down" ? "text-down" : "ink text-ink"
        }`}
      >
        {value}
      </p>
      {note && <p className="mut text-[10px] text-muted">{note}</p>}
    </div>
  );
}

function TearsheetPortfolioSection({
  section,
  pageBreak,
}: {
  section: TearsheetSection;
  pageBreak: boolean;
}) {
  const a = section.portfolio;
  const c = section.commentary;
  const ccy = a.base_currency;
  const research = new Map(section.holdings_analysis.map((h) => [h.ticker, h]));

  return (
    <section className={`space-y-5 ${pageBreak ? "print-page-break" : ""}`}>
      <div className="flex items-baseline justify-between gap-3 border-b border-grid pb-2">
        <h2 className="ink text-xl font-bold tracking-tight text-ink">{a.name}</h2>
        <span className="mut text-xs text-muted">
          {a.positions.length} positions · base {ccy} · benchmark {a.benchmark}
        </span>
      </div>

      {/* Executive summary */}
      <SheetBlock title="Executive summary">
        <p className="ink2 text-sm leading-relaxed text-ink2">{c.executive_summary}</p>
      </SheetBlock>

      {/* Headline band */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        <SheetStat label="Market value" value={formatMoney(a.market_value, ccy)} />
        <SheetStat
          label="Total return"
          value={`${a.total_return >= 0 ? "+" : ""}${formatMoney(a.total_return, ccy)}`}
          tone={a.total_return >= 0 ? "up" : "down"}
        />
        <SheetStat
          label="TWR"
          value={a.risk.twr_pct != null ? `${a.risk.twr_pct >= 0 ? "+" : ""}${a.risk.twr_pct}%` : "—"}
          tone={a.risk.twr_pct != null ? (a.risk.twr_pct >= 0 ? "up" : "down") : undefined}
        />
        <SheetStat
          label="Benchmark"
          value={
            a.risk.benchmark_return_pct != null
              ? `${a.risk.benchmark_return_pct >= 0 ? "+" : ""}${a.risk.benchmark_return_pct}%`
              : "—"
          }
        />
        <SheetStat
          label="Volatility"
          value={a.risk.volatility_pct != null ? `${a.risk.volatility_pct}%` : "—"}
        />
        <SheetStat
          label="Sharpe"
          value={a.risk.sharpe != null ? String(a.risk.sharpe) : "—"}
        />
      </div>

      {/* Performance */}
      <div className="grid gap-4 lg:grid-cols-2">
        <SheetBlock title="Portfolio value vs invested capital">
          <ValueChart data={a.performance} currency={ccy} height={230} />
        </SheetBlock>
        <SheetBlock title={`Time-weighted return vs ${a.benchmark}`}>
          <TwrChart data={a.performance} benchmarkLabel={a.benchmark} height={230} />
        </SheetBlock>
      </div>
      <SheetBlock title="Performance commentary">
        <p className="ink2 text-sm leading-relaxed text-ink2">{c.performance}</p>
      </SheetBlock>

      {/* Risk + allocation */}
      <div className="grid gap-4 lg:grid-cols-2">
        <SheetBlock title="Risk assessment">
          <p className="ink2 mb-4 text-sm leading-relaxed text-ink2">{c.risk}</p>
          <dl className="grid grid-cols-3 gap-3 border-t border-grid pt-3">
            <SheetMiniStat label="Max drawdown" value={fmtPct(a.risk.max_drawdown_pct)} />
            <SheetMiniStat label="Beta" value={a.risk.beta != null ? String(a.risk.beta) : "—"} />
            <SheetMiniStat label="Best / worst day" value={`${fmtPct(a.risk.best_day_pct)} / ${fmtPct(a.risk.worst_day_pct)}`} />
          </dl>
        </SheetBlock>
        <SheetBlock title="Attribution — top contributors & detractors">
          <ContributorsBar
            contributors={a.top_contributors}
            detractors={a.top_detractors}
            currency={ccy}
            height={210}
          />
        </SheetBlock>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <SheetBlock title="Sector allocation">
          <AllocationDonut data={a.sector_allocation} currency={ccy} height={200} />
        </SheetBlock>
        <SheetBlock title="Currency exposure">
          <AllocationDonut data={a.currency_allocation} currency={ccy} height={200} />
        </SheetBlock>
      </div>
      <SheetBlock title="Allocation commentary">
        <p className="ink2 text-sm leading-relaxed text-ink2">{c.allocation}</p>
      </SheetBlock>

      {/* Holdings table */}
      <SheetBlock title="Holdings">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-xs">
            <thead className="text-left uppercase tracking-wider text-muted">
              <tr className="border-b border-grid">
                <th className="py-2 pr-3">Instrument</th>
                <th className="px-3 py-2 text-right">Weight</th>
                <th className="px-3 py-2 text-right">Shares</th>
                <th className="px-3 py-2 text-right">Avg cost</th>
                <th className="px-3 py-2 text-right">Price</th>
                <th className="px-3 py-2 text-right">P&L</th>
                <th className="px-3 py-2 text-right">Research</th>
              </tr>
            </thead>
            <tbody>
              {a.positions.map((p) => {
                const r = research.get(p.ticker);
                return (
                  <tr key={p.ticker} className="border-b border-grid/60">
                    <td className="py-2 pr-3">
                      <span className="ink font-semibold text-ink">{p.ticker}</span>
                      {p.name && (
                        <span className="mut ml-2 hidden text-muted sm:inline">
                          {p.name}
                        </span>
                      )}
                    </td>
                    <td className="tnum px-3 py-2 text-right text-ink2">
                      {p.weight_pct != null ? `${p.weight_pct.toFixed(1)}%` : "—"}
                    </td>
                    <td className="tnum px-3 py-2 text-right text-ink2">{p.shares}</td>
                    <td className="tnum px-3 py-2 text-right text-ink2">
                      {formatMoney(p.avg_cost, ccy)}
                    </td>
                    <td className="tnum px-3 py-2 text-right text-ink2">
                      {p.current_price != null ? formatMoney(p.current_price, ccy) : "—"}
                    </td>
                    <td
                      className={`tnum px-3 py-2 text-right ${
                        (p.unrealized_pnl ?? 0) >= 0 ? "text-up" : "text-down"
                      }`}
                    >
                      {p.unrealized_pnl != null
                        ? `${p.unrealized_pnl >= 0 ? "+" : ""}${formatMoney(p.unrealized_pnl, ccy)}`
                        : "—"}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {r?.trend_label ? <TrendBadge label={r.trend_label} /> : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </SheetBlock>

      {/* Holding commentary */}
      <SheetBlock title="Position review">
        <div className="space-y-3">
          {c.holdings.map((h) => (
            <div key={h.ticker} className="border-b border-grid/60 pb-3 last:border-0 last:pb-0">
              <p className="ink text-sm font-semibold text-ink">
                {h.ticker}
                {h.name && (
                  <span className="ink2 ml-2 font-normal text-ink2">{h.name}</span>
                )}
                {h.weight_pct != null && (
                  <span className="mut ml-2 text-xs font-normal text-muted">
                    {h.weight_pct.toFixed(1)}% of portfolio
                  </span>
                )}
              </p>
              <p className="ink2 mt-1 text-xs leading-relaxed text-ink2">{h.text}</p>
            </div>
          ))}
        </div>
      </SheetBlock>

      {/* Outlook */}
      <SheetBlock title="Outlook & action items">
        <ul className="space-y-2">
          {c.outlook.map((item) => (
            <li key={item} className="ink2 flex items-start gap-2 text-sm text-ink2">
              <span className="text-accent">▸</span>
              {item}
            </li>
          ))}
        </ul>
      </SheetBlock>
    </section>
  );
}

function SheetBlock({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="sheet-panel rounded-2xl border border-grid bg-panel p-5">
      <h3 className="ink mb-3 text-[11px] font-semibold uppercase tracking-widest text-ink">
        {title}
      </h3>
      {children}
    </div>
  );
}

function SheetStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "up" | "down";
}) {
  return (
    <div className="sheet-panel rounded-xl border border-grid bg-panel px-4 py-3">
      <p className="mut text-[10px] font-medium uppercase tracking-widest text-muted">
        {label}
      </p>
      <p
        className={`tnum mt-0.5 text-base font-semibold ${
          tone === "up" ? "text-up" : tone === "down" ? "text-down" : "ink text-ink"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

function SheetMiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="mut text-[10px] font-medium uppercase tracking-widest text-muted">
        {label}
      </dt>
      <dd className="tnum ink mt-0.5 text-sm font-semibold text-ink">{value}</dd>
    </div>
  );
}

function fmtPct(value?: number | null): string {
  if (value == null) return "—";
  return `${value > 0 ? "+" : ""}${value}%`;
}

// ---------------------------------------------------------------------------
// Market (screener) report
// ---------------------------------------------------------------------------

function MarketReport({
  report,
  content,
}: {
  report: ReportDetail;
  content: MarketReportContent;
}) {
  return (
    <article className="space-y-4">
      <header className="sheet-panel rounded-2xl border border-grid bg-panel p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="ink text-2xl font-bold tracking-tight text-ink">
              {content.label}
            </h1>
            <p className="ink2 mt-1 text-sm text-ink2">{content.description}</p>
          </div>
          <div className="text-right text-xs text-muted">
            <p>{new Date(report.created_at).toLocaleString()}</p>
            {content.stale && (
              <p className="mt-1">
                <Badge tone="warn">Stale data</Badge>
              </p>
            )}
          </div>
        </div>
      </header>

      <div className="overflow-x-auto rounded-2xl border border-grid">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="bg-panel text-left text-[11px] uppercase tracking-wider text-muted">
            <tr>
              <th className="px-4 py-3">Ticker</th>
              <th className="px-4 py-3">Company</th>
              <th className="px-4 py-3 text-right">Price</th>
              <th className="px-4 py-3 text-right">Change</th>
              <th className="px-4 py-3 text-right">Mkt cap</th>
              <th className="px-4 py-3">Trend</th>
              <th className="px-4 py-3">Sentiment</th>
              <th className="px-4 py-3 text-right">Analyst upside</th>
            </tr>
          </thead>
          <tbody>
            {content.stocks.map((stock) => {
              const upside = stock.analyst_upside_pct as number | null;
              return (
                <tr
                  key={String(stock.ticker)}
                  className="border-t border-grid hover:bg-panel/60"
                >
                  <td className="px-4 py-2.5">
                    <Link
                      to={`/stock/${stock.ticker}`}
                      className="font-semibold text-ink hover:text-accent"
                    >
                      {String(stock.ticker)}
                    </Link>
                  </td>
                  <td className="max-w-[240px] truncate px-4 py-2.5 text-ink2">
                    {String(stock.company ?? "—")}
                  </td>
                  <td className="tnum px-4 py-2.5 text-right text-ink2">
                    {String(stock.price ?? "—")}
                  </td>
                  <td
                    className={`tnum px-4 py-2.5 text-right ${
                      String(stock.change ?? "").startsWith("-")
                        ? "text-down"
                        : "text-up"
                    }`}
                  >
                    {String(stock.change ?? "—")}
                  </td>
                  <td className="tnum px-4 py-2.5 text-right text-ink2">
                    {String(stock.market_cap ?? "—")}
                  </td>
                  <td className="px-4 py-2.5">
                    <TrendBadge label={stock.trend_label as string} />
                  </td>
                  <td className="px-4 py-2.5 text-ink2">
                    {String(stock.sentiment_label ?? "—")}
                  </td>
                  <td className="tnum px-4 py-2.5 text-right text-ink2">
                    {upside != null ? `${upside > 0 ? "+" : ""}${upside}%` : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </article>
  );
}
