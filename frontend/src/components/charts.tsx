import { useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AllocationSlice, ContributorEntry, PerformancePoint } from "../types";
import { formatMoney } from "../utils/currency";

// Categorical series — dark-mode steps in fixed order (validated palette)
export const SERIES = [
  "#3987e5",
  "#008300",
  "#d55181",
  "#c98500",
  "#199e70",
  "#d95926",
  "#9085e9",
  "#e66767",
] as const;

const INK = "#ffffff";
const INK2 = "#c3c2b7";
const MUTED = "#898781";
const GRID = "#2c2c2a";
const SURFACE = "#1a1a19";

const tooltipStyle = {
  backgroundColor: "#232321",
  border: "1px solid #383835",
  borderRadius: 12,
  color: INK,
  fontSize: 12,
  padding: "8px 12px",
} as const;

function shortDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
}

function fullDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function compactMoney(value: number, currency: string): string {
  const abs = Math.abs(value);
  const symbol = { EUR: "€", USD: "$", GBP: "£" }[currency] ?? `${currency} `;
  if (abs >= 1_000_000) return `${symbol}${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 10_000) return `${symbol}${(value / 1_000).toFixed(0)}k`;
  if (abs >= 1_000) return `${symbol}${(value / 1_000).toFixed(1)}k`;
  return `${symbol}${value.toFixed(0)}`;
}

// ---------------------------------------------------------------------------
// Portfolio value vs invested capital
// ---------------------------------------------------------------------------

export function ValueChart({
  data,
  currency,
  height = 280,
}: {
  data: PerformancePoint[];
  currency: string;
  height?: number;
}) {
  if (data.length < 2) return <ChartEmpty />;
  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 4 }}>
          <defs>
            <linearGradient id="valueFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={SERIES[0]} stopOpacity={0.25} />
              <stop offset="100%" stopColor={SERIES[0]} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={GRID} strokeDasharray="0" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={shortDate}
            tick={{ fill: MUTED, fontSize: 11 }}
            axisLine={{ stroke: GRID }}
            tickLine={false}
            minTickGap={48}
          />
          <YAxis
            tickFormatter={(v: number) => compactMoney(v, currency)}
            tick={{ fill: MUTED, fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={62}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            labelFormatter={(label) => fullDate(String(label))}
            formatter={(value, name) => [
              formatMoney(Number(value), currency),
              name === "value" ? "Market value" : "Invested capital",
            ]}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke={SERIES[0]}
            strokeWidth={2}
            fill="url(#valueFill)"
            dot={false}
            activeDot={{ r: 4, stroke: SURFACE, strokeWidth: 2 }}
          />
          <Line
            type="stepAfter"
            dataKey="cost_basis"
            stroke={MUTED}
            strokeWidth={1.5}
            strokeDasharray="5 4"
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
      <ChartLegend
        items={[
          { label: "Market value", color: SERIES[0] },
          { label: "Invested capital", color: MUTED, dashed: true },
        ]}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// TWR index vs benchmark (both indexed to 100)
// ---------------------------------------------------------------------------

export function TwrChart({
  data,
  benchmarkLabel,
  height = 280,
}: {
  data: PerformancePoint[];
  benchmarkLabel: string;
  height?: number;
}) {
  const points = data.filter((p) => p.twr_index != null);
  if (points.length < 2) return <ChartEmpty />;
  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 4 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={shortDate}
            tick={{ fill: MUTED, fontSize: 11 }}
            axisLine={{ stroke: GRID }}
            tickLine={false}
            minTickGap={48}
          />
          <YAxis
            domain={["auto", "auto"]}
            tickFormatter={(v: number) => `${(v - 100).toFixed(0)}%`}
            tick={{ fill: MUTED, fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={48}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            labelFormatter={(label) => fullDate(String(label))}
            formatter={(value, name) => [
              `${(Number(value) - 100).toFixed(2)}%`,
              name === "twr_index" ? "Portfolio (TWR)" : benchmarkLabel,
            ]}
          />
          <Line
            type="monotone"
            dataKey="twr_index"
            stroke={SERIES[0]}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, stroke: SURFACE, strokeWidth: 2 }}
          />
          <Line
            type="monotone"
            dataKey="benchmark"
            stroke={SERIES[3]}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, stroke: SURFACE, strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
      <ChartLegend
        items={[
          { label: "Portfolio (TWR)", color: SERIES[0] },
          { label: benchmarkLabel, color: SERIES[3] },
        ]}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Allocation donut (max 7 slices + Other, fixed hue order)
// ---------------------------------------------------------------------------

export function AllocationDonut({
  data,
  currency,
  height = 240,
}: {
  data: AllocationSlice[];
  currency: string;
  height?: number;
}) {
  const [active, setActive] = useState<number | null>(null);
  if (!data.length) return <ChartEmpty />;

  const shown = data.slice(0, 7);
  const rest = data.slice(7);
  const slices = [...shown];
  if (rest.length) {
    slices.push({
      label: "Other",
      value: rest.reduce((s, r) => s + r.value, 0),
      weight_pct: rest.reduce((s, r) => s + r.weight_pct, 0),
    });
  }

  return (
    <div className="flex flex-col items-center gap-2 sm:flex-row sm:gap-6">
      <ResponsiveContainer width="100%" height={height} className="max-w-[240px]">
        <PieChart>
          <Pie
            data={slices}
            dataKey="value"
            nameKey="label"
            innerRadius="62%"
            outerRadius="92%"
            paddingAngle={2}
            stroke={SURFACE}
            strokeWidth={2}
            onMouseEnter={(_, i) => setActive(i)}
            onMouseLeave={() => setActive(null)}
          >
            {slices.map((slice, i) => (
              <Cell
                key={slice.label}
                fill={SERIES[i % SERIES.length]}
                opacity={active === null || active === i ? 1 : 0.35}
              />
            ))}
          </Pie>
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(value, _name, entry) => [
              `${formatMoney(Number(value), currency)} · ${(
                entry?.payload as AllocationSlice
              )?.weight_pct.toFixed(1)}%`,
              (entry?.payload as AllocationSlice)?.label,
            ]}
          />
        </PieChart>
      </ResponsiveContainer>
      <ul className="w-full space-y-1.5 text-sm">
        {slices.map((slice, i) => (
          <li
            key={slice.label}
            className="flex items-center justify-between gap-3"
            onMouseEnter={() => setActive(i)}
            onMouseLeave={() => setActive(null)}
          >
            <span className="flex min-w-0 items-center gap-2">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-[3px]"
                style={{ background: SERIES[i % SERIES.length] }}
              />
              <span className="truncate text-ink2">{slice.label}</span>
            </span>
            <span className="tnum shrink-0 text-ink">
              {slice.weight_pct.toFixed(1)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Contributors / detractors horizontal bars
// ---------------------------------------------------------------------------

export function ContributorsBar({
  contributors,
  detractors,
  currency,
  height,
}: {
  contributors: ContributorEntry[];
  detractors: ContributorEntry[];
  currency: string;
  height?: number;
}) {
  const rows = [...contributors, ...[...detractors].reverse()];
  if (!rows.length) return <ChartEmpty />;
  const chartHeight = height ?? Math.max(140, rows.length * 34 + 20);
  return (
    <ResponsiveContainer width="100%" height={chartHeight}>
      <BarChart
        data={rows}
        layout="vertical"
        margin={{ top: 0, right: 16, bottom: 0, left: 8 }}
        barSize={14}
      >
        <CartesianGrid stroke={GRID} horizontal={false} />
        <XAxis
          type="number"
          tickFormatter={(v: number) => compactMoney(v, currency)}
          tick={{ fill: MUTED, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="ticker"
          tick={{ fill: INK2, fontSize: 12 }}
          axisLine={{ stroke: GRID }}
          tickLine={false}
          width={72}
        />
        <Tooltip
          cursor={{ fill: "rgba(255,255,255,0.04)" }}
          contentStyle={tooltipStyle}
          formatter={(value) => [formatMoney(Number(value), currency), "Total P&L"]}
        />
        <Bar dataKey="total_pnl" radius={[0, 4, 4, 0]}>
          {rows.map((row) => (
            <Cell
              key={row.ticker}
              fill={row.total_pnl >= 0 ? "#0ca30c" : "#d03b3b"}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------

function ChartLegend({
  items,
}: {
  items: { label: string; color: string; dashed?: boolean }[];
}) {
  return (
    <div className="mt-2 flex flex-wrap items-center gap-4 px-1">
      {items.map((item) => (
        <span key={item.label} className="flex items-center gap-1.5 text-xs text-ink2">
          <span
            className="inline-block h-0.5 w-4 rounded"
            style={{
              background: item.dashed
                ? `repeating-linear-gradient(90deg, ${item.color} 0 4px, transparent 4px 7px)`
                : item.color,
            }}
          />
          {item.label}
        </span>
      ))}
    </div>
  );
}

function ChartEmpty() {
  return (
    <div className="flex h-40 items-center justify-center text-sm text-muted">
      Not enough data to chart yet
    </div>
  );
}
