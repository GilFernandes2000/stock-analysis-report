import { useEffect, useState } from "react";
import { api } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { ReportViewer } from "../components/ReportViewer";
import { StaleBadge } from "../components/StaleBadge";
import { usePageTitle } from "../hooks/usePageTitle";
import type { ReportDetail, ReportSummary } from "../types";

export function Reports() {
  usePageTitle("Reports");
  const [summaries, setSummaries] = useState<ReportSummary[]>([]);
  const [selected, setSelected] = useState<ReportDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listReports()
      .then(setSummaries)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function selectReport(id: number) {
    try {
      const report = await api.getReport(id);
      setSelected(report);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load report");
    }
  }

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    try {
      await api.generateReports();
      const updated = await api.listReports();
      setSummaries(updated);
      if (updated[0]) await selectReport(updated[0].id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate reports");
    } finally {
      setGenerating(false);
    }
  }

  if (loading) return <LoadingSkeleton rows={5} />;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white">Reports</h1>
          <p className="mt-2 text-slate-400">
            Trend reports generated from Finviz screener presets.
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {generating ? "Generating..." : "Generate all reports"}
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-red-300">
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-2 lg:col-span-1">
          {summaries.length === 0 ? (
            <p className="text-slate-500">No reports yet.</p>
          ) : (
            summaries.map((s) => (
              <button
                key={s.id}
                onClick={() => selectReport(s.id)}
                className={`w-full rounded-xl border p-4 text-left transition ${
                  selected?.id === s.id
                    ? "border-emerald-500/50 bg-emerald-500/10"
                    : "border-slate-800 bg-slate-900/40 hover:border-slate-600"
                }`}
              >
                <p className="font-medium text-white">{s.title}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {s.report_type} · {new Date(s.created_at).toLocaleString()}
                </p>
              </button>
            ))
          )}
        </div>

        <div className="lg:col-span-2">
          {selected ? (
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
              {selected.content_json.stale && (
                <div className="mb-4">
                  <StaleBadge />
                </div>
              )}
              <ReportViewer markdown={selected.content_markdown} />
            </div>
          ) : (
            <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-slate-800 text-slate-500">
              Select a report to view details
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
