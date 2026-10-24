import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import {
  ACCESS_SERIES,
  AXIS_TEXT,
  EVENT_TYPE_COLORS,
  GRID,
  LOGIN_SERIES,
  OTHER,
  shortDay,
} from '../../utils/charts';
import { StackedBars } from '../analytics/AnalyticsCharts';
import { ChartCard, ChartTooltip } from '../analytics/AnalyticsParts';

const sum = (rows, key) => rows.reduce((total, row) => total + row[key], 0);
const axisProps = { tick: { fill: AXIS_TEXT, fontSize: 11 }, tickLine: false, axisLine: false };
const dayTable = (rows, series) => ({
  columns: [{ key: 'day', label: 'Day' }, ...series.map((s) => ({ key: s.key, label: s.label }))],
  rows: rows.map((row) => ({ ...row, day: shortDay(row.date) })),
});

/** Successful vs failed logins per day (mockup: Login Activity). */
export function LoginActivityChart({ days }) {
  const legend = LOGIN_SERIES.map((s) => ({ ...s, value: sum(days, s.key) }));
  return (
    <ChartCard
      title="Login activity"
      legend={legend}
      empty={legend.every((s) => s.value === 0)}
      emptyText="No logins in this period."
      table={dayTable(days, LOGIN_SERIES)}
    >
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={days} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="date" tickFormatter={shortDay} minTickGap={24} {...axisProps} />
            <YAxis allowDecimals={false} {...axisProps} />
            <Tooltip
              content={<ChartTooltip labelFormatter={shortDay} />}
              cursor={{ stroke: AXIS_TEXT, strokeDasharray: '3 3' }}
            />
            {LOGIN_SERIES.map((s) => (
              <Area
                key={s.key}
                dataKey={s.key}
                name={s.label}
                stroke={s.color}
                strokeWidth={2}
                fill={s.color}
                fillOpacity={0.12}
                dot={false}
                activeDot={{ r: 4, stroke: '#ffffff', strokeWidth: 2 }}
                isAnimationActive={false}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  );
}

/** Unauthorized and blocked attempts per day (mockup: Access Attempts). */
export function AccessAttemptsChart({ days }) {
  const legend = ACCESS_SERIES.map((s) => ({ ...s, value: sum(days, s.key) }));
  return (
    <ChartCard
      title="Access attempts"
      legend={legend}
      empty={legend.every((s) => s.value === 0)}
      emptyText="No unauthorized or blocked attempts in this period."
      table={dayTable(days, ACCESS_SERIES)}
    >
      <StackedBars days={days} series={ACCESS_SERIES} />
    </ChartCard>
  );
}

/** Security events by type (mockup: donut with the total in the middle). */
export function EventsByTypeChart({ types }) {
  const total = types.reduce((t, row) => t + row.count, 0);
  const main = types.filter((t) => EVENT_TYPE_COLORS[t.type]);
  const other = types.filter((t) => !EVENT_TYPE_COLORS[t.type]);
  const slices = [
    ...main.map((t) => ({ ...t, color: EVENT_TYPE_COLORS[t.type] })),
    ...(other.length
      ? [
          {
            type: 'other',
            label: 'Other',
            count: other.reduce((n, t) => n + t.count, 0),
            color: OTHER,
          },
        ]
      : []),
  ];
  return (
    <ChartCard
      title="Security events"
      empty={total === 0}
      emptyText="No security events in this period."
      table={{
        columns: [
          { key: 'label', label: 'Type' },
          { key: 'count', label: 'Events' },
        ],
        rows: types,
      }}
    >
      <div className="flex flex-col items-center gap-4 sm:flex-row lg:flex-col">
        <div className="relative size-40 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={slices}
                dataKey="count"
                nameKey="label"
                innerRadius="66%"
                outerRadius="100%"
                stroke="#ffffff"
                strokeWidth={2}
                isAnimationActive={false}
              >
                {slices.map((slice) => (
                  <Cell key={slice.type} fill={slice.color} />
                ))}
              </Pie>
              <Tooltip content={<ChartTooltip />} />
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-xl font-semibold text-slate-900">{total}</span>
            <span className="text-xs text-slate-500">events</span>
          </div>
        </div>
        <ul className="w-full space-y-1.5 text-sm">
          {slices.map((s) => (
            <li key={s.type} className="flex items-center gap-2">
              <span className="size-2.5 shrink-0 rounded-sm" style={{ background: s.color }} />
              <span className="truncate text-slate-700">{s.label}</span>
              <span className="ml-auto text-slate-900">{s.count}</span>
              <span className="w-10 text-right text-xs text-slate-500">
                {Math.round((s.count / total) * 100)}%
              </span>
            </li>
          ))}
        </ul>
      </div>
    </ChartCard>
  );
}
