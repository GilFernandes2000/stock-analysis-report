import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { StockTable, type TableRow } from "../components/StockTable";
import { Button, EmptyState, ErrorNote, inputClass, LoadingSkeleton, Spinner, StaleBadge } from "../components/ui";
import { useDisplayCurrency } from "../hooks/useDisplayCurrency";
import { useFavorites } from "../favorites/FavoritesContext";
import { usePageTitle } from "../hooks/usePageTitle";
import type { Quote } from "../types";

function toRow(q: Quote): TableRow {
  return {
    ticker: q.ticker,
    name: q.name,
    sector: q.sector,
    price: q.price,
    priceCurrency: q.display_currency,
    nativePrice: q.native_price,
    nativeCurrency: q.native_currency,
    changePct: q.change_pct,
    marketCap: q.market_cap,
    pe: q.pe,
  };
}

export function Favorites() {
  usePageTitle("Favorites");
  const { tickers, add, error: favError } = useFavorites();
  const { currency } = useDisplayCurrency();
  const [quotes, setQuotes] = useState<Quote[] | null>(null);
  const [stale, setStale] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [adding, setAdding] = useState(false);

  const favCount = tickers.size;

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .favoriteQuotes()
      .then((res) => {
        setQuotes(res.quotes);
        setStale(res.stale);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  // Reload when the favorite set changes (add/remove) or currency switches.
  useEffect(() => {
    if (favCount === 0) {
      setQuotes([]);
      setLoading(false);
      return;
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [favCount, currency]);

  async function handleAdd(e: FormEvent) {
    e.preventDefault();
    const t = input.trim().toUpperCase();
    if (!t) return;
    setAdding(true);
    try {
      await add(t);
      setInput("");
    } finally {
      setAdding(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">Favorites</h1>
          <p className="mt-1 text-sm text-muted">
            Your watchlist — live quotes for the stocks you follow. Sort any column;
            click a ticker for full research, sentiment and insider activity.
          </p>
        </div>
        <form onSubmit={handleAdd} className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value.toUpperCase())}
            placeholder="Add ticker — NVDA, ASML.AS…"
            className={`${inputClass} w-52`}
          />
          <Button type="submit" disabled={adding || !input.trim()}>
            {adding ? "Adding…" : "Add"}
          </Button>
        </form>
      </div>

      {(error || favError) && <ErrorNote message={error || favError!} />}

      {favCount > 0 && (
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted">
            {favCount} stock{favCount === 1 ? "" : "s"} tracked
          </span>
          {stale && <StaleBadge />}
          {loading && <Spinner label="Refreshing quotes…" />}
        </div>
      )}

      {loading && !quotes ? (
        <LoadingSkeleton rows={4} />
      ) : favCount === 0 ? (
        <EmptyState
          title="No favorites yet"
          hint="Star a stock anywhere in the app — on the Market movers, the Screener, or a stock's research page — or add a ticker above. It'll show up here with live quotes."
        />
      ) : quotes && quotes.length > 0 ? (
        <StockTable rows={quotes.map(toRow)} defaultSort="marketCap" />
      ) : (
        <EmptyState
          title="Couldn't load quotes"
          hint="Your favorites are saved, but quotes didn't load. Try refreshing — the market data source may be rate-limited."
        />
      )}
    </div>
  );
}
