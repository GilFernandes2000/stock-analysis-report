import type { ReactNode } from "react";

export function Panel({
  children,
  className = "",
  title,
  action,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  action?: ReactNode;
}) {
  return (
    <section
      className={`sheet-panel rounded-2xl border border-grid bg-panel p-5 ${className}`}
    >
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {title && (
            <h3 className="ink text-sm font-semibold uppercase tracking-wider text-ink">
              {title}
            </h3>
          )}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatCard({
  label,
  value,
  sub,
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: "neutral" | "up" | "down";
}) {
  const valueColor =
    tone === "up" ? "text-up" : tone === "down" ? "text-down" : "text-ink";
  return (
    <div className="sheet-panel rounded-2xl border border-grid bg-panel px-5 py-4">
      <p className="mut text-[11px] font-medium uppercase tracking-wider text-muted">
        {label}
      </p>
      <p className={`ink mt-1 text-2xl font-semibold tnum ${valueColor}`}>{value}</p>
      {sub && <div className="ink2 mt-1 text-xs text-ink2">{sub}</div>}
    </div>
  );
}

export function DeltaText({
  value,
  suffix = "%",
  className = "",
}: {
  value?: number | null;
  suffix?: string;
  className?: string;
}) {
  if (value == null) return <span className={`text-muted ${className}`}>—</span>;
  const tone = value > 0 ? "text-up" : value < 0 ? "text-down" : "text-ink2";
  return (
    <span className={`tnum ${tone} ${className}`}>
      {value > 0 ? "+" : ""}
      {value.toFixed(2)}
      {suffix}
    </span>
  );
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "up" | "down" | "warn" | "accent";
}) {
  const styles = {
    neutral: "border-edge bg-raised text-ink2",
    up: "border-up/40 bg-up/10 text-up",
    down: "border-down/40 bg-down/10 text-down",
    warn: "border-warn/40 bg-warn/10 text-warn",
    accent: "border-accent/40 bg-accent/10 text-accent",
  }[tone];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${styles}`}
    >
      {children}
    </span>
  );
}

export function TrendBadge({ label }: { label?: string | null }) {
  if (!label) return null;
  const tone =
    label === "Bullish" ? "up" : label === "Bearish" ? "down" : "neutral";
  return <Badge tone={tone}>{label}</Badge>;
}

export function StaleBadge() {
  return <Badge tone="warn">Stale data</Badge>;
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-crit/40 bg-crit/10 px-4 py-3 text-sm text-down">
      {message}
    </div>
  );
}

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-edge px-6 py-14 text-center">
      <p className="font-medium text-ink">{title}</p>
      {hint && <p className="max-w-md text-sm text-muted">{hint}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function LoadingSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="animate-pulse space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-20 rounded-2xl bg-panel" />
      ))}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-muted">
      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-edge border-t-accent" />
      {label}
    </span>
  );
}

export function Button({
  children,
  onClick,
  disabled,
  variant = "primary",
  type = "button",
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "ghost" | "danger";
  type?: "button" | "submit";
  className?: string;
}) {
  const styles = {
    primary:
      "bg-accent text-white hover:bg-accent-soft disabled:opacity-40 border border-transparent",
    ghost:
      "border border-edge text-ink2 hover:border-accent/60 hover:text-ink disabled:opacity-40 bg-transparent",
    danger:
      "border border-crit/50 text-down hover:bg-crit/10 disabled:opacity-40 bg-transparent",
  }[variant];
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-xl px-4 py-2 text-sm font-medium transition ${styles} ${className}`}
    >
      {children}
    </button>
  );
}

export const inputClass =
  "w-full rounded-xl border border-edge bg-inset px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none";

export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wider text-muted">
        {label}
      </span>
      {children}
    </label>
  );
}
