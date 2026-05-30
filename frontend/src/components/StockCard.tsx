import { Link } from "react-router-dom";
import type { ScreenerStockRow } from "../types";
import { TrendBadge } from "./TrendBadge";

interface StockCardProps {
  ticker: string;
  company?: string | null;
  price?: string | number | null;
  change?: string | null;
  trendLabel?: string;
  extra?: string;
}

export function StockCard({
  ticker,
  company,
  price,
  change,
  trendLabel,
  extra,
}: StockCardProps) {
  const changeColor =
    change && change.startsWith("-") ? "text-red-400" : "text-emerald-400";

  return (
    <Link
      to={`/stock/${ticker}`}
      className="block rounded-xl border border-slate-800 bg-slate-900/60 p-4 transition hover:border-slate-600 hover:bg-slate-900"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold text-white">{ticker}</h3>
          {company && (
            <p className="text-sm text-slate-400 line-clamp-1">{company}</p>
          )}
        </div>
        {trendLabel && <TrendBadge label={trendLabel} />}
      </div>
      <div className="mt-3 flex items-baseline gap-3">
        {price != null && (
          <span className="text-xl font-mono text-white">${price}</span>
        )}
        {change && <span className={`text-sm ${changeColor}`}>{change}</span>}
      </div>
      {extra && <p className="mt-2 text-xs text-slate-500">{extra}</p>}
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
