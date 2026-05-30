interface TrendBadgeProps {
  label: string;
  className?: string;
}

const styles: Record<string, string> = {
  Bullish: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  Bearish: "bg-red-500/20 text-red-300 border-red-500/40",
  Neutral: "bg-slate-500/20 text-slate-300 border-slate-500/40",
  Unknown: "bg-amber-500/20 text-amber-300 border-amber-500/40",
};

export function TrendBadge({ label, className = "" }: TrendBadgeProps) {
  const style = styles[label] ?? styles.Neutral;
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${style} ${className}`}
    >
      {label}
    </span>
  );
}
