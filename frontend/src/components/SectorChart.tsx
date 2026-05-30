interface SectorChartProps {
  allocation: Array<{ sector: string; weight_pct: number; value: number }>;
}

const COLORS = [
  "#34d399",
  "#60a5fa",
  "#f472b6",
  "#fbbf24",
  "#a78bfa",
  "#fb7185",
  "#2dd4bf",
];

export function SectorChart({ allocation }: SectorChartProps) {
  if (!allocation.length) {
    return (
      <p className="text-sm text-slate-500">No sector allocation data yet.</p>
    );
  }

  return (
    <div className="space-y-3">
      {allocation.map((item, i) => (
        <div key={item.sector}>
          <div className="mb-1 flex justify-between text-sm">
            <span className="text-slate-300">{item.sector}</span>
            <span className="font-mono text-slate-400">
              {item.weight_pct.toFixed(1)}%
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-800">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${Math.min(item.weight_pct, 100)}%`,
                backgroundColor: COLORS[i % COLORS.length],
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
