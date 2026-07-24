import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import {
  Badge,
  Button,
  EmptyState,
  ErrorNote,
  LoadingSkeleton,
  Panel,
} from "../components/ui";
import { usePageTitle } from "../hooks/usePageTitle";
import type { PortfolioSummary, ReportSummary } from "../types";

export function Reports() {
  usePageTitle("Reports");
  const navigate = useNavigate();
  const [reports, setReports] = useState<ReportSummary[] | null>(null);
  const [portfolios, setPortfolios] = useState<PortfolioSummary[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [marketBusy, setMarketBusy] = useState(false);

  const load = useCallback(() => {
    api
      .listReports()
      .then(setReports)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
    api
      .listPortfolios(false)
      .then((list) => {
        setPortfolios(list);
        setSelected(new Set(list.filter((p) => p.transaction_count > 0).map((p) => p.id)));
      })
      .catch(() => undefined);
  }, []);

  useEffect(load, [load]);

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleTearsheet() {
    setBusy(true);
    setError(null);
    try {
      const report = await api.generateTearsheet([...selected]);
      navigate(`/reports/${report.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Report generation failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleMarketReports() {
    setMarketBusy(true);
    setError(null);
    try {
      await api.generateReports();
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setMarketBusy(false);
    }
  }

  async function handleDelete(id: number) {
    if (!window.confirm("Delete this report?")) return;
    await api.deleteReport(id);
    load();
  }

  const tearsheets = (reports ?? []).filter((r) => r.kind === "portfolio");
  const marketReports = (reports ?? []).filter((r) => r.kind !== "portfolio");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink">Reports</h1>
        <p className="mt-1 text-sm text-muted">
          Institutional-style tearsheets for your portfolios, plus scheduled market
          screening reports.
        </p>
      </div>

      {error && <ErrorNote message={error} />}

      <Panel title="Generate portfolio tearsheet">
        {portfolios.length === 0 ? (
          <p className="text-sm text-muted">
            Create a portfolio and import transactions first.
          </p>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-ink2">
              Select the portfolio(s) to cover. Multi-select produces one document
              with a combined overview and a full section per portfolio.
            </p>
            <div className="flex flex-wrap gap-2">
              {portfolios.map((p) => {
                const empty = p.transaction_count === 0;
                const active = selected.has(p.id);
                return (
                  <button
                    key={p.id}
                    disabled={empty}
                    onClick={() => toggle(p.id)}
                    className={`rounded-xl border px-4 py-2 text-sm font-medium transition disabled:opacity-40 ${
                      active
                        ? "border-accent bg-accent/10 text-accent"
                        : "border-edge text-ink2 hover:border-accent/50"
                    }`}
                    title={empty ? "No transactions yet" : undefined}
                  >
                    {active ? "✓ " : ""}
                    {p.name}
                  </button>
                );
              })}
            </div>
            <Button onClick={handleTearsheet} disabled={busy || selected.size === 0}>
              {busy
                ? "Building tearsheet… (fetching market data)"
                : `Generate tearsheet (${selected.size})`}
            </Button>
          </div>
        )}
      </Panel>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-ink">
          Portfolio tearsheets
        </h2>
        {reports === null ? (
          <LoadingSkeleton rows={2} />
        ) : tearsheets.length === 0 ? (
          <EmptyState
            title="No tearsheets yet"
            hint="Generate your first professional portfolio report above."
          />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {tearsheets.map((r) => (
              <ReportCard key={r.id} report={r} onDelete={() => handleDelete(r.id)} />
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-ink">
            Market reports
          </h2>
          <Button variant="ghost" onClick={handleMarketReports} disabled={marketBusy}>
            {marketBusy ? "Generating… (slow)" : "Refresh market reports"}
          </Button>
        </div>
        {reports === null ? (
          <LoadingSkeleton rows={2} />
        ) : marketReports.length === 0 ? (
          <EmptyState
            title="No market reports yet"
            hint="Market reports scan Finviz screener presets on weekday mornings, or on demand."
          />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {marketReports.map((r) => (
              <ReportCard key={r.id} report={r} onDelete={() => handleDelete(r.id)} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function ReportCard({
  report,
  onDelete,
}: {
  report: ReportSummary;
  onDelete: () => void;
}) {
  return (
    <div className="group relative rounded-2xl border border-grid bg-panel p-4 transition hover:border-accent/50">
      <Link to={`/reports/${report.id}`} className="block">
        <div className="flex items-start justify-between gap-2">
          <Badge tone={report.kind === "portfolio" ? "accent" : "neutral"}>
            {report.kind === "portfolio" ? "Tearsheet" : report.report_type}
          </Badge>
          <span className="text-[11px] text-muted">
            {new Date(report.created_at).toLocaleDateString()}
          </span>
        </div>
        <p className="mt-2 line-clamp-2 text-sm font-medium text-ink group-hover:text-accent">
          {report.title}
        </p>
        <p className="mt-1 text-xs text-muted">
          {new Date(report.created_at).toLocaleTimeString()}
        </p>
      </Link>
      <button
        onClick={onDelete}
        className="absolute bottom-3 right-3 hidden rounded px-1.5 py-0.5 text-xs text-muted hover:text-down group-hover:block"
        title="Delete report"
      >
        ✕
      </button>
    </div>
  );
}
