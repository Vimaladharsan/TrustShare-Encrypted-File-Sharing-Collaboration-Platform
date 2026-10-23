import {
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
} from 'recharts';

import {
  AXIS_TEXT,
  CATEGORY_SERIES,
  DOWNLOAD_SERIES,
  GRID,
  SHARE_SERIES,
  shortDay,
} from '../../utils/charts';
import { formatBytes } from '../../utils/format';
import { ChartCard, ChartTooltip } from './AnalyticsParts';

const sum = (rows, key) => rows.reduce((total, row) => total + row[key], 0);
const axisProps = { tick: { fill: AXIS_TEXT, fontSize: 11 }, tickLine: false, axisLine: false };
const dayTable = (rows, series) => ({
  columns: [{ key: 'day', label: 'Day' }, ...series.map((s) => ({ key: s.key, label: s.label }))],
  rows: rows.map((row) => ({ ...row, day: shortDay(row.date) })),
});

/** Donut of storage by file type, with the total in the middle (mockup: Storage Usage). */
export function StorageDonut({ usage, quotaBytes }) {
  const used = usage.reduce((total, row) => total + row.bytes, 0);
  const slices = CATEGORY_SERIES.map((s) => ({
    ...s,
    bytes: usage.find((row) => row.category === s.key)?.bytes ?? 0,
    files: usage.find((row) => row.category === s.key)?.files ?? 0,
  }));
  const shown = slices.filter((s) => s.bytes > 0);
  return (
    <ChartCard
      title="Storage usage by file type"
      empty={used === 0}
      emptyText="No files stored yet."
      table={{
        columns: [
          { key: 'label', label: 'Type' },
          { key: 'files', label: 'Files' },
          { key: 'size', label: 'Size' },
        ],
        rows: slices.map((s) => ({ ...s, size: formatBytes(s.bytes) })),
      }}
    >
      <div className="flex flex-col items-center gap-6 sm:flex-row">
        <div className="relative size-48 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={shown}
                dataKey="bytes"
                nameKey="label"
                innerRadius="68%"
                outerRadius="100%"
                stroke="#ffffff"
                strokeWidth={2}
                isAnimationActive={false}
              >
                {shown.map((slice) => (
                  <Cell key={slice.key} fill={slice.color} />
                ))}
              </Pie>
              <Tooltip content={<ChartTooltip valueFormatter={formatBytes} />} />
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-lg font-semibold text-slate-900">{formatBytes(used)}</span>
            <span className="text-xs text-slate-500">of {formatBytes(quotaBytes)}</span>
          </div>
        </div>
        <ul className="w-full space-y-2 text-sm">
          {slices.map((s) => (
            <li key={s.key} className="flex items-center gap-2">
              <span className="size-2.5 rounded-sm" style={{ background: s.color }} />
              <span className="text-slate-700">{s.label}</span>
              <span className="ml-auto text-slate-900">{formatBytes(s.bytes)}</span>
              <span className="w-12 text-right text-xs text-slate-500">
                {used ? Math.round((s.bytes / used) * 100) : 0}%
              </span>
            </li>
          ))}
        </ul>
      </div>
    </ChartCard>
  );
}

/** Stacked bars: files uploaded per day, by type (mockup: File Upload Reports). */
export function UploadsChart({ days }) {
  const legend = CATEGORY_SERIES.map((s) => ({ ...s, value: sum(days, s.key) }));
  const total = legend.reduce((t, s) => t + s.value, 0);
  return (
    <ChartCard
      title="File uploads"
      legend={legend}
      empty={total === 0}
      emptyText="No uploads in this period."
      table={dayTable(days, CATEGORY_SERIES)}
    >
      <StackedBars days={days} series={CATEGORY_SERIES} />
    </ChartCard>
  );
}

/** Lines: total downloads, unique users, downloads through shares (mockup: Download Analytics). */
export function DownloadsChart({ days }) {
  const legend = DOWNLOAD_SERIES.map((s) => ({ ...s, value: sum(days, s.key) }));
  legend[1] = { ...legend[1], value: undefined }; // unique users don't add up across days
  return (
    <ChartCard
      title="Downloads of your files"
      legend={legend}
      empty={sum(days, 'total') === 0}
      emptyText="No downloads in this period."
      table={dayTable(days, DOWNLOAD_SERIES)}
    >
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={days} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="date" tickFormatter={shortDay} minTickGap={24} {...axisProps} />
            <YAxis allowDecimals={false} {...axisProps} />
            <Tooltip
              content={<ChartTooltip labelFormatter={shortDay} />}
              cursor={{ stroke: AXIS_TEXT, strokeDasharray: '3 3' }}
            />
            {DOWNLOAD_SERIES.map((s) => (
              <Line
                key={s.key}
                dataKey={s.key}
                name={s.label}
                stroke={s.color}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, stroke: '#ffffff', strokeWidth: 2 }}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  );
}

/** Stacked bars: shares created per day, link vs direct (mockup: Sharing Activity Reports). */
export function SharesChart({ days }) {
  const legend = SHARE_SERIES.map((s) => ({ ...s, value: sum(days, s.key) }));
  return (
    <ChartCard
      title="Sharing activity"
      legend={legend}
      empty={legend.every((s) => s.value === 0)}
      emptyText="You didn't share anything in this period."
      table={dayTable(days, SHARE_SERIES)}
    >
      <StackedBars days={days} series={SHARE_SERIES} />
    </ChartCard>
  );
}

export function StackedBars({ days, series }) {
  return (
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={days} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="date" tickFormatter={shortDay} minTickGap={24} {...axisProps} />
          <YAxis allowDecimals={false} {...axisProps} />
          <Tooltip
            content={<ChartTooltip labelFormatter={shortDay} />}
            cursor={{ fill: '#f1f5f9' }}
          />
          {series.map((s, index) => (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.label}
              stackId="day"
              fill={s.color}
              maxBarSize={18}
              stroke="#ffffff"
              strokeWidth={1}
              // Only the top segment gets rounded corners.
              radius={index === series.length - 1 ? [4, 4, 0, 0] : 0}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
