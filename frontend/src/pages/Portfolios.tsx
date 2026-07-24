import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import {
  Button,
  DeltaText,
  EmptyState,
  ErrorNote,
  Field,
  inputClass,
  LoadingSkeleton,
  Spinner,
} from "../components/ui";
import { usePageTitle } from "../hooks/usePageTitle";
import type { PortfolioSummary } from "../types";
import { formatMoney } from "../utils/currency";

const BROKER_LABELS: Record<string, string> = {
  degiro: "Degiro",
  trading212: "Trading 212",
  manual: "Manual",
};

const BENCHMARKS = [
  { value: "^GSPC", label: "S&P 500 (^GSPC)" },
  { value: "^STOXX50E", label: "Euro Stoxx 50" },
  { value: "IWDA.AS", label: "MSCI World (IWDA)" },
  { value: "^IXIC", label: "Nasdaq Composite" },
  { value: "^FTSE", label: "FTSE 100" },
];

export function Portfolios() {
  usePageTitle("Portfolios");
  const [portfolios, setPortfolios] = useState<PortfolioSummary[] | null>(null);
  const [quotesLoading, setQuotesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const load = useCallback(async () => {
    try {
      // fast structural load first, then live valuation
      const basic = await api.listPortfolios(false);
      setPortfolios(basic);
      if (basic.length) {
        setQuotesLoading(true);
        const quoted = await api.listPortfolios(true);
        setPortfolios(quoted);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load portfolios");
    } finally {
      setQuotesLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">Portfolios</h1>
          <p className="mt-1 text-sm text-muted">
            Import from Degiro or Trading 212, or track positions manually.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {quotesLoading && <Spinner label="Fetching quotes…" />}
          <Button onClick={() => setShowCreate(true)}>New portfolio</Button>
        </div>
      </div>

      {error && <ErrorNote message={error} />}

      {portfolios === null ? (
        <LoadingSkeleton rows={3} />
      ) : portfolios.length === 0 ? (
        <EmptyState
          title="No portfolios yet"
          hint="Create your first portfolio, then import your broker's transaction history CSV to unlock performance, dividends and risk analytics."
          action={<Button onClick={() => setShowCreate(true)}>Create portfolio</Button>}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {portfolios.map((p) => (
            <PortfolioCard key={p.id} portfolio={p} />
          ))}
        </div>
      )}

      {showCreate && (
        <CreatePortfolioModal
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            load();
          }}
        />
      )}
    </div>
  );
}

function PortfolioCard({ portfolio }: { portfolio: PortfolioSummary }) {
  return (
    <Link
      to={`/portfolios/${portfolio.id}`}
      className="group rounded-2xl border border-grid bg-panel p-5 transition hover:border-accent/50"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate font-semibold text-ink group-hover:text-accent">
            {portfolio.name}
          </h3>
          <p className="mt-0.5 text-xs text-muted">
            {BROKER_LABELS[portfolio.broker] ?? portfolio.broker} ·{" "}
            {portfolio.base_currency} · {portfolio.position_count} position
            {portfolio.position_count === 1 ? "" : "s"}
          </p>
        </div>
        {portfolio.day_change_pct != null && (
          <DeltaText value={portfolio.day_change_pct} className="text-sm" />
        )}
      </div>
      <div className="mt-4">
        {portfolio.market_value != null ? (
          <>
            <p className="tnum text-2xl font-semibold text-ink">
              {formatMoney(portfolio.market_value, portfolio.base_currency)}
            </p>
            <p className="mt-0.5 text-sm">
              {portfolio.total_return != null && (
                <span
                  className={`tnum ${
                    portfolio.total_return >= 0 ? "text-up" : "text-down"
                  }`}
                >
                  {portfolio.total_return >= 0 ? "+" : ""}
                  {formatMoney(portfolio.total_return, portfolio.base_currency)}
                </span>
              )}{" "}
              {portfolio.total_return_pct != null && (
                <DeltaText value={portfolio.total_return_pct} className="text-xs" />
              )}
            </p>
          </>
        ) : portfolio.transaction_count === 0 ? (
          <p className="text-sm text-muted">
            Empty — import a broker CSV to get started
          </p>
        ) : (
          <p className="text-sm text-muted">
            {portfolio.transaction_count} transactions
          </p>
        )}
      </div>
    </Link>
  );
}

function CreatePortfolioModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [broker, setBroker] = useState("degiro");
  const [baseCurrency, setBaseCurrency] = useState("EUR");
  const [benchmark, setBenchmark] = useState("^GSPC");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createPortfolio({
        name,
        broker,
        base_currency: baseCurrency,
        benchmark,
      });
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create portfolio");
      setBusy(false);
    }
  }

  return (
    <Modal title="New portfolio" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label="Name">
          <input
            className={inputClass}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Degiro — Long term"
            required
            autoFocus
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Broker">
            <select
              className={inputClass}
              value={broker}
              onChange={(e) => setBroker(e.target.value)}
            >
              <option value="degiro">Degiro</option>
              <option value="trading212">Trading 212</option>
              <option value="manual">Manual</option>
            </select>
          </Field>
          <Field label="Base currency">
            <select
              className={inputClass}
              value={baseCurrency}
              onChange={(e) => setBaseCurrency(e.target.value)}
            >
              <option>EUR</option>
              <option>USD</option>
              <option>GBP</option>
            </select>
          </Field>
        </div>
        <Field label="Benchmark">
          <select
            className={inputClass}
            value={benchmark}
            onChange={(e) => setBenchmark(e.target.value)}
          >
            {BENCHMARKS.map((b) => (
              <option key={b.value} value={b.value}>
                {b.label}
              </option>
            ))}
          </select>
        </Field>
        {error && <ErrorNote message={error} />}
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={busy || !name.trim()}>
            {busy ? "Creating…" : "Create"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function Modal({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-4 backdrop-blur-sm sm:items-center"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className={`my-8 w-full rounded-2xl border border-edge bg-panel p-6 shadow-2xl ${
          wide ? "max-w-4xl" : "max-w-md"
        }`}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-ink">{title}</h2>
          <button
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-muted transition hover:bg-raised hover:text-ink"
            aria-label="Close"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
