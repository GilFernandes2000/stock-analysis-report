import { Link } from "react-router-dom";
import type { ScreenerStockRow } from "../types";
import { formatMoney, getDisplayCurrency } from "../utils/currency";
import { TrendBadge } from "./ui";

interface StockCardProps {
  ticker: string;
  company?: string | null;
  price?: string | number | null;
  change?: string | null;
  trendLabel?: string;
  extra?: string;
  currency?: string | null;
}

export function StockCard({
  ticker,
  company,
  price,
  change,
  trendLabel,
  extra,
  currency,
}: StockCardProps) {
  const changeColor =
    change && change.startsWith("-") ? "text-down" : "text-up";

  const priceLabel =
    price != null
      ? typeof price === "number"
        ? formatMoney(price, currency ?? getDisplayCurrency())
        : price
      : null;

  return (
    <Link
      to={`/stock/${ticker}`}
      className="block rounded-2xl border border-grid bg-panel p-4 transition hover:border-accent/50"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="font-semibold text-ink">{ticker}</h3>
          {company && (
            <p className="truncate text-xs text-muted">{company}</p>
          )}
        </div>
        {trendLabel && <TrendBadge label={trendLabel} />}
      </div>
      <div className="mt-3 flex items-baseline gap-3">
        {priceLabel != null && (
          <span className="tnum text-lg font-semibold text-ink">{priceLabel}</span>
        )}
        {change && <span className={`tnum text-sm ${changeColor}`}>{change}</span>}
      </div>
      {extra && <p className="mt-2 text-xs text-muted">{extra}</p>}
    </Link>
  );
}

export function ScreenerStockCard({ stock }: { stock: ScreenerStockRow }) {
  return (
    <StockCard
      ticker={stock.ticker}
      company={stock.company}
      price={stock.price}
      change={stock.change}
    />
  );
}
