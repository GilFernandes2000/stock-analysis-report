import { useState } from "react";
import { api } from "../../api/client";
import { Badge, Button, ErrorNote } from "../../components/ui";
import type { ImportPreview } from "../../types";
import { Modal } from "../Portfolios";

export function ImportWizard({
  portfolioId,
  onClose,
  onImported,
}: {
  portfolioId: number;
  onClose: () => void;
  onImported: () => void;
}) {
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  async function handleFile(file: File) {
    setBusy(true);
    setError(null);
    try {
      const result = await api.importPreview(portfolioId, file);
      if (result.broker === "unknown") {
        setError(result.warnings.join(" "));
      } else {
        setPreview(result);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to parse file");
    } finally {
      setBusy(false);
    }
  }

  function updateTicker(index: number, ticker: string) {
    if (!preview) return;
    const rows = [...preview.rows];
    rows[index] = { ...rows[index], ticker: ticker.toUpperCase(), ticker_resolved: !!ticker };
    setPreview({ ...preview, rows });
  }

  async function handleCommit() {
    if (!preview) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.importCommit(portfolioId, preview.rows, true);
      window.alert(
        `Imported ${result.imported} transactions (${result.skipped} skipped).`
      );
      onImported();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
      setBusy(false);
    }
  }

  const newRows = preview?.rows.filter((r) => !r.duplicate).length ?? 0;
  const needsMapping =
    preview?.rows.filter((r) => !r.duplicate && r.ticker == null && r.isin).length ?? 0;

  return (
    <Modal title="Import broker history" onClose={onClose} wide>
      {!preview ? (
        <div className="space-y-4">
          <p className="text-sm text-ink2">
            Upload the transaction-history CSV from your broker. Supported exports:
          </p>
          <ul className="space-y-1.5 text-sm text-muted">
            <li>
              <span className="font-medium text-ink2">Degiro</span> — Inbox →
              Account statements → <code className="text-accent">Transactions.csv</code>{" "}
              (trades) and <code className="text-accent">Account.csv</code> (dividends,
              deposits, fees)
            </li>
            <li>
              <span className="font-medium text-ink2">Trading 212</span> — History →
              Export CSV (include all event types)
            </li>
          </ul>
          <label
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              const file = e.dataTransfer.files[0];
              if (file) handleFile(file);
            }}
            className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-6 py-12 text-center transition ${
              dragOver ? "border-accent bg-accent/5" : "border-edge hover:border-accent/50"
            }`}
          >
            <span className="text-2xl">⇪</span>
            <span className="text-sm font-medium text-ink">
              {busy ? "Parsing…" : "Drop a CSV here or click to browse"}
            </span>
            <span className="text-xs text-muted">
              Files are parsed locally on your server — nothing leaves your machine.
            </span>
            <input
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFile(file);
              }}
            />
          </label>
          {error && <ErrorNote message={error} />}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="accent">
              {preview.broker === "trading212" ? "Trading 212" : "Degiro"} ·{" "}
              {preview.file_kind}
            </Badge>
            <Badge tone="neutral">{preview.total_rows} rows</Badge>
            {preview.duplicate_count > 0 && (
              <Badge tone="warn">{preview.duplicate_count} duplicates skipped</Badge>
            )}
            {needsMapping > 0 && (
              <Badge tone="down">{needsMapping} tickers need mapping</Badge>
            )}
          </div>

          {preview.warnings.length > 0 && (
            <div className="space-y-1 rounded-xl border border-warn/30 bg-warn/5 px-4 py-3">
              {preview.warnings.map((w) => (
                <p key={w} className="text-xs text-warn">
                  {w}
                </p>
              ))}
            </div>
          )}

          <div className="max-h-[45vh] overflow-auto rounded-xl border border-grid">
            <table className="w-full min-w-[760px] text-xs">
              <thead className="sticky top-0 bg-raised text-left uppercase tracking-wider text-muted">
                <tr>
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Ticker</th>
                  <th className="px-3 py-2">Name / ISIN</th>
                  <th className="px-3 py-2 text-right">Shares</th>
                  <th className="px-3 py-2 text-right">Amount</th>
                  <th className="px-3 py-2 text-right">Fees</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row, i) => (
                  <tr
                    key={`${row.external_id}-${i}`}
                    className={`border-t border-grid ${
                      row.duplicate ? "opacity-40" : ""
                    }`}
                  >
                    <td className="tnum whitespace-nowrap px-3 py-1.5 text-ink2">
                      {new Date(row.date).toLocaleDateString()}
                    </td>
                    <td className="px-3 py-1.5 capitalize text-ink2">
                      {row.type}
                      {row.duplicate && (
                        <span className="ml-1 text-muted">(dup)</span>
                      )}
                    </td>
                    <td className="px-3 py-1.5">
                      {["buy", "sell", "dividend", "tax"].includes(row.type) ? (
                        <input
                          value={row.ticker ?? ""}
                          onChange={(e) => updateTicker(i, e.target.value)}
                          placeholder="map…"
                          className={`w-24 rounded-md border bg-inset px-2 py-1 text-xs text-ink focus:border-accent focus:outline-none ${
                            row.ticker ? "border-edge" : "border-crit/60"
                          }`}
                        />
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td className="max-w-[220px] truncate px-3 py-1.5 text-muted">
                      {row.name ?? row.note ?? ""}{" "}
                      {row.isin && <span className="text-[10px]">({row.isin})</span>}
                    </td>
                    <td className="tnum px-3 py-1.5 text-right text-ink2">
                      {row.shares ?? "—"}
                    </td>
                    <td
                      className={`tnum px-3 py-1.5 text-right ${
                        row.amount > 0 ? "text-up" : "text-ink2"
                      }`}
                    >
                      {row.amount > 0 ? "+" : ""}
                      {row.amount.toFixed(2)}
                    </td>
                    <td className="tnum px-3 py-1.5 text-right text-ink2">
                      {row.fees ? row.fees.toFixed(2) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {error && <ErrorNote message={error} />}

          <div className="flex items-center justify-between gap-3">
            <button
              onClick={() => setPreview(null)}
              className="text-sm text-muted hover:text-ink2"
            >
              ← Choose a different file
            </button>
            <Button onClick={handleCommit} disabled={busy || newRows === 0}>
              {busy
                ? "Importing…"
                : `Import ${newRows} transaction${newRows === 1 ? "" : "s"}`}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
