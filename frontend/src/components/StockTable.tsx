import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useFavorites } from "../favorites/FavoritesContext";
import { formatMoney } from "../utils/currency";

// A single normalized row the table can render, produced from either a
// screener row or a quote.
export interface TableRow {
  ticker: string;
  name?: string | null;
  sector?: string | null;
  price?: number | null;
  priceCurrency?: string | null;
  changePct?: number | null;
  marketCap?: number | null;
  pe?: number | null;
  // optional preformatted native price (e.g. GBp listings)
  nativePrice?: number | null;
  nativeCurrency?: string | null;
}

type ColumnKey = "ticker" | "name" | "sector" | "price" | "changePct" | "marketCap" | "pe";

interface Column {
  key: ColumnKey;
  label: string;
  numeric: boolean;
  className?: string;
  hideBelow?: "sm" | "lg";
}

const COLUMNS: Column[] = [
  { key: "ticker", label: "Ticker", numeric: false },
  { key: "name", label: "Name", numeric: false, hideBelow: "sm" },
  { key: "sector", label: "Sector", numeric: false, hideBelow: "lg" },
  { key: "price", label: "Price", numeric: true, className: "text-right" },
  { key: "changePct", label: "Change", numeric: true, className: "text-right" },
  { key: "marketCap", label: "Mkt cap", numeric: true, className: "text-right", hideBelow: "sm" },
  { key: "pe", label: "P/E", numeric: true, className: "text-right", hideBelow: "lg" },
];

function hideClass(hideBelow?: "sm" | "lg"): string {
  if (hideBelow === "sm") return "hidden sm:table-cell";
  if (hideBelow === "lg") return "hidden lg:table-cell";
  return "";
}

function compactCap(value?: number | null): string {
  if (value == null) return "—";
  if (value >= 1e12) return `${(value / 1e12).toFixed(2)}T`;
  if (value >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(0)}M`;
  return String(Math.round(value));
}

export function StarButton({ ticker }: { ticker: string }) {
  const { isFavorite, toggle } = useFavorites();
  const active = isFavorite(ticker);
  return (
    <button
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        toggle(ticker);
      }}
      aria-label={active ? "Remove from favorites" : "Add to favorites"}
      title={active ? "Remove from favorites" : "Add to favorites"}
      className={`text-base leading-none transition ${
        active ? "text-warn" : "text-edge hover:text-muted"
      }`}
    >
      {active ? "★" : "☆"}
    </button>
  );
}

export function StockTable({
  rows,
  emptyMessage = "No stocks to show.",
  defaultSort = "marketCap",
}: {
  rows: TableRow[];
  emptyMessage?: string;
  defaultSort?: ColumnKey;
}) {
  const [sortKey, setSortKey] = useState<ColumnKey>(defaultSort);
  const [asc, setAsc] = useState(false);

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = valueFor(a, sortKey);
      const bv = valueFor(b, sortKey);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "string" && typeof bv === "string") {
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return asc ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
    return copy;
  }, [rows, sortKey, asc]);

  function toggleSort(key: ColumnKey) {
    if (key === sortKey) {
      setAsc((v) => !v);
    } else {
      setSortKey(key);
      // text columns default ascending, numeric default descending
      setAsc(key === "ticker" || key === "name" || key === "sector");
    }
  }

  if (rows.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-edge px-6 py-12 text-center text-sm text-muted">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-grid">
      <table className="w-full min-w-[640px] text-sm">
        <thead className="bg-panel text-left text-[11px] uppercase tracking-wider text-muted">
          <tr>
            <th className="w-8 px-3 py-3" />
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                className={`px-4 py-3 ${col.className ?? ""} ${hideClass(col.hideBelow)}`}
              >
                <button
                  onClick={() => toggleSort(col.key)}
                  className={`inline-flex items-center gap-1 transition hover:text-ink ${
                    sortKey === col.key ? "text-ink" : ""
                  } ${col.numeric ? "flex-row-reverse" : ""}`}
                >
                  {col.label}
                  <span className="text-[9px]">
                    {sortKey === col.key ? (asc ? "▲" : "▼") : ""}
                  </span>
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr
              key={row.ticker}
              className="border-t border-grid transition hover:bg-panel/60"
            >
              <td className="px-3 py-2.5 text-center">
                <StarButton ticker={row.ticker} />
              </td>
              <Cell>
                <Link
                  to={`/stock/${row.ticker}`}
                  className="font-semibold text-ink hover:text-accent"
                >
                  {row.ticker}
                </Link>
              </Cell>
              <Cell hide="sm">
                <span className="block max-w-[220px] truncate text-ink2">
                  {row.name ?? "—"}
                </span>
              </Cell>
              <Cell hide="lg">
                <span className="text-ink2">{row.sector ?? "—"}</span>
              </Cell>
              <Cell className="text-right">
                <span className="tnum text-ink">
                  {row.price != null
                    ? formatMoney(row.price, row.priceCurrency)
                    : "—"}
                </span>
                {row.nativeCurrency &&
                  row.nativePrice != null &&
                  row.nativeCurrency !== row.priceCurrency && (
                    <span className="block text-[11px] text-muted">
                      {formatMoney(row.nativePrice, row.nativeCurrency)}
                    </span>
                  )}
              </Cell>
              <Cell className="text-right">
                <ChangePct value={row.changePct} />
              </Cell>
              <Cell className="text-right" hide="sm">
                <span className="tnum text-ink2">{compactCap(row.marketCap)}</span>
              </Cell>
              <Cell className="text-right" hide="lg">
                <span className="tnum text-ink2">
                  {row.pe != null ? row.pe.toFixed(1) : "—"}
                </span>
              </Cell>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Cell({
  children,
  className = "",
  hide,
}: {
  children: ReactNode;
  className?: string;
  hide?: "sm" | "lg";
}) {
  return (
    <td className={`px-4 py-2.5 ${className} ${hideClass(hide)}`}>{children}</td>
  );
}

function ChangePct({ value }: { value?: number | null }) {
  if (value == null) return <span className="text-muted">—</span>;
  const tone = value > 0 ? "text-up" : value < 0 ? "text-down" : "text-ink2";
  return (
    <span className={`tnum ${tone}`}>
      {value > 0 ? "+" : ""}
      {value.toFixed(2)}%
    </span>
  );
}

function valueFor(row: TableRow, key: ColumnKey): string | number | null | undefined {
  switch (key) {
    case "ticker":
      return row.ticker;
    case "name":
      return row.name ?? "";
    case "sector":
      return row.sector ?? "";
    case "price":
      return row.price;
    case "changePct":
      return row.changePct;
    case "marketCap":
      return row.marketCap;
    case "pe":
      return row.pe;
  }
}
