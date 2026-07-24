import type { InsiderSignal } from "../types";
import { Badge } from "./ui";

export function InsiderBadge({ signal }: { signal?: InsiderSignal | null }) {
  if (!signal) return null;
  const tone =
    signal.label === "Bullish"
      ? "up"
      : signal.label === "Bearish"
        ? "down"
        : "neutral";
  return (
    <Badge tone={tone}>
      Insiders: {signal.label === "No activity" ? "quiet" : signal.label}
    </Badge>
  );
}

function usd(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `$${(value / 1_000).toFixed(0)}k`;
  return `$${value.toFixed(0)}`;
}

export function InsiderSignalCard({ signal }: { signal: InsiderSignal }) {
  return (
    <div className="sheet-panel rounded-2xl border border-grid bg-panel p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="ink text-sm font-semibold uppercase tracking-wider text-ink">
          Insider activity — last {Math.round(signal.window_days / 30)} months
        </h3>
        <InsiderBadge signal={signal} />
      </div>
      <p className="ink2 mt-2 text-sm text-ink2">{signal.summary}</p>

      {signal.label !== "No activity" && (
        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div>
            <p className="mut text-[10px] font-medium uppercase tracking-widest text-muted">
              Open-market buys
            </p>
            <p className="tnum mt-0.5 text-lg font-semibold text-up">
              {signal.buy_count}
              <span className="ml-1.5 text-xs font-normal text-ink2">
                {usd(signal.buy_value)}
              </span>
            </p>
          </div>
          <div>
            <p className="mut text-[10px] font-medium uppercase tracking-widest text-muted">
              Sales
            </p>
            <p className="tnum mt-0.5 text-lg font-semibold text-down">
              {signal.sell_count}
              <span className="ml-1.5 text-xs font-normal text-ink2">
                {usd(signal.sell_value)}
              </span>
            </p>
          </div>
          <div>
            <p className="mut text-[10px] font-medium uppercase tracking-widest text-muted">
              Distinct buyers / sellers
            </p>
            <p className="tnum ink mt-0.5 text-lg font-semibold text-ink">
              {signal.buyers} / {signal.sellers}
            </p>
          </div>
          <div>
            <p className="mut text-[10px] font-medium uppercase tracking-widest text-muted">
              Net flow
            </p>
            <p
              className={`tnum mt-0.5 text-lg font-semibold ${
                signal.net_value > 0
                  ? "text-up"
                  : signal.net_value < 0
                    ? "text-down"
                    : "text-ink"
              }`}
            >
              {signal.net_value > 0 ? "+" : ""}
              {usd(signal.net_value)}
            </p>
          </div>
        </div>
      )}

      {signal.signals.length > 0 && (
        <ul className="mt-4 space-y-1.5 border-t border-grid pt-3">
          {signal.signals.map((s) => (
            <li key={s} className="ink2 flex items-start gap-2 text-xs text-ink2">
              <span
                className={
                  signal.label === "Bearish" ? "text-down" : "text-accent"
                }
              >
                ▸
              </span>
              {s}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
