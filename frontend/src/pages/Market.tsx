import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { StockCard } from "../components/StockCard";
import {
  Button,
  EmptyState,
  ErrorNote,
  LoadingSkeleton,
  StaleBadge,
} from "../components/ui";
import { usePageTitle } from "../hooks/usePageTitle";
import type { MarketReportContent, ReportDetail } from "../types";

export function Market() {
  usePageTitle("Market");
  const [reports, setReports] = useState<ReportDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    api
      .latestReports()
      .then(setReports)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function refreshReports() {
    setGenerating(true);
    setError(null);
    try {
      await api.generateReports();
      setReports(await api.latestReports());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to refresh reports");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">Market</h1>
          <p className="mt-1 text-sm text-muted">
            Latest ideas from the Finviz screener scans — search any ticker above for
            a full research view.
          </p>
        </div>
        <Button variant="ghost" onClick={refreshReports} disabled={generating}>
          {generating ? "Scanning… (slow)" : "Refresh scans"}
        </Button>
      </div>

      {error && <ErrorNote message={error} />}

      {loading ? (
        <LoadingSkeleton rows={4} />
      ) : reports.length === 0 ? (
        <EmptyState
          title="No market scans yet"
          hint="Run the screener scans to surface momentum, technical and analyst-favorite ideas. Scans also run automatically on weekday mornings."
          action={
            <Button onClick={refreshReports} disabled={generating}>
              Run scans now
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {reports.map((report) => {
            const content = report.content_json as MarketReportContent;
            return (
              <section
                key={report.id}
                className="rounded-2xl border border-grid bg-panel p-5"
              >
                <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                  <Link
                    to={`/reports/${report.id}`}
                    className="font-semibold text-ink hover:text-accent"
                  >
                    {report.title}
                  </Link>
                  <div className="flex items-center gap-2">
                    {content.stale && <StaleBadge />}
                    <span className="text-[11px] text-muted">
                      {new Date(report.created_at).toLocaleString()}
                    </span>
                  </div>
                </div>
                <p className="mb-4 text-xs text-muted">{content.description}</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {content.stocks.slice(0, 4).map((stock) => (
                    <StockCard
                      key={String(stock.ticker)}
                      ticker={String(stock.ticker)}
                      company={String(stock.company ?? "")}
                      price={stock.price as string | number | null}
                      change={stock.change as string | null}
                      trendLabel={stock.trend_label as string | undefined}
                      extra={
                        stock.sentiment_label
                          ? `Sentiment: ${stock.sentiment_label}`
                          : undefined
                      }
                    />
                  ))}
                </div>
                <Link
                  to={`/reports/${report.id}`}
                  className="mt-3 inline-block text-xs text-accent hover:underline"
                >
                  Full report →
                </Link>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
