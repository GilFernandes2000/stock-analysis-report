import { useEffect, useState } from "react";
import { api } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { StockCard } from "../components/StockCard";
import { StaleBadge } from "../components/StaleBadge";
import { usePageTitle } from "../hooks/usePageTitle";
import type { ReportDetail } from "../types";

export function Dashboard() {
  usePageTitle("Dashboard");
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
      const updated = await api.latestReports();
      setReports(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to refresh reports");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="space-y-8">
      <section>
        <h1 className="text-3xl font-bold text-white">Dashboard</h1>
        <p className="mt-2 text-slate-400">
          Use the header search for any ticker, or browse latest trend reports below.
        </p>
      </section>

      {error && (
        <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-red-300">
          {error}
        </div>
      )}

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-white">Latest Reports</h2>
          <button
            onClick={refreshReports}
            disabled={generating}
            className="text-sm text-emerald-400 hover:text-emerald-300 disabled:opacity-50"
          >
            {generating ? "Generating..." : "Refresh reports"}
          </button>
        </div>
        {loading ? (
          <LoadingSkeleton rows={4} />
        ) : reports.length === 0 ? (
          <p className="text-slate-500">
            No reports yet. Click &quot;Refresh reports&quot; to generate.
          </p>
        ) : (
          <div className="grid gap-6 lg:grid-cols-2">
            {reports.map((report) => (
              <div
                key={report.id}
                className="rounded-xl border border-slate-800 bg-slate-900/40 p-5"
              >
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <h3 className="font-semibold text-white">{report.title}</h3>
                  <div className="flex items-center gap-2">
                    {report.content_json.stale && <StaleBadge />}
                    <span className="text-xs text-slate-500">
                      {new Date(report.created_at).toLocaleString()}
                    </span>
                  </div>
                </div>
                <p className="mb-4 text-sm text-slate-400">
                  {report.content_json.description}
                </p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {report.content_json.stocks.slice(0, 4).map((stock) => (
                    <StockCard
                      key={String(stock.ticker)}
                      ticker={String(stock.ticker)}
                      company={String(stock.company ?? "")}
                      price={stock.price as string | number | null}
                      change={stock.change as string | null}
                      trendLabel={String(stock.trend_label ?? "")}
                      extra={
                        stock.sentiment_label
                          ? `Sentiment: ${stock.sentiment_label}`
                          : undefined
                      }
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
