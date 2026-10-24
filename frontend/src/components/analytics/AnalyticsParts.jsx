import { ArrowDownRight, ArrowUpRight, CalendarDays, Table2 } from 'lucide-react';
import { useState } from 'react';

import { changeLabel, isoDay, presetRange } from '../../utils/charts';
import Button from '../Button';

/** A headline number with its change vs the previous period (mockup: 4 cards on top).
 * `upIsBad`: for failures and threats a rise is shown in red, a drop in green. */
export function SummaryCard({ icon: Icon, tone, label, value, sub, metric, upIsBad = false }) {
  const change = metric ? changeLabel(metric) : null;
  const up = metric && metric.value >= metric.previous;
  const good = metric && (metric.value === metric.previous || up !== upIsBad);
  return (
    <div className="card hover:shadow-card-hover flex min-w-0 flex-col p-5 transition">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-slate-500">{label}</p>
        <span
          className={`grid size-10 shrink-0 place-items-center rounded-xl ring-1 ring-black/5 ring-inset ${tone}`}
        >
          <Icon className="size-5" aria-hidden="true" />
        </span>
      </div>
      <p className="mt-1 text-[28px] leading-tight font-semibold tracking-tight text-slate-950">
        {value}
      </p>
      <div className="mt-auto flex flex-wrap items-center gap-x-2 gap-y-1 pt-2 text-xs text-slate-500">
        <span>{sub}</span>
        {change && (
          <span
            className={`inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 font-semibold ring-1 ring-inset ${
              good
                ? 'bg-emerald-50 text-emerald-700 ring-emerald-600/15'
                : 'bg-red-50 text-red-700 ring-red-600/15'
            }`}
            title="Compared with the previous period of the same length"
          >
            {up ? <ArrowUpRight className="size-3" /> : <ArrowDownRight className="size-3" />}
            {change} vs previous
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * A chart panel: title, legend, the chart – and a "Table" toggle that shows the same numbers as
 * a table (accessible alternative to colour; also handy for exact values).
 * table: { columns: [{ key, label }], rows: [...] }
 */
export function ChartCard({ title, legend, table, empty, emptyText, children }) {
  const [showTable, setShowTable] = useState(false);
  return (
    <section className="card min-w-0 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <h2 className="font-semibold text-slate-900">{title}</h2>
        {table && !empty && (
          <button
            type="button"
            onClick={() => setShowTable((v) => !v)}
            aria-pressed={showTable}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-800"
          >
            <Table2 className="size-3.5" aria-hidden="true" />
            {showTable ? 'Chart' : 'Table'}
          </button>
        )}
      </div>
      {legend && !empty && !showTable && <Legend items={legend} />}
      {empty ? (
        <p className="flex h-56 items-center justify-center text-sm text-slate-500">{emptyText}</p>
      ) : showTable ? (
        <DataTable {...table} />
      ) : (
        children
      )}
    </section>
  );
}

export function Legend({ items }) {
  return (
    <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm" style={{ background: item.color }} />
          {item.label}
          {item.value !== undefined && (
            <span className="font-medium text-slate-900">{item.value}</span>
          )}
        </li>
      ))}
    </ul>
  );
}

function DataTable({ columns, rows }) {
  return (
    <div className="max-h-64 overflow-auto">
      <table className="w-full text-left text-xs">
        <thead className="sticky top-0 bg-slate-50 text-slate-500">
          <tr>
            {columns.map((col) => (
              <th key={col.key} className="px-2 py-1.5 font-medium">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 text-slate-700">
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((col) => (
                <td key={col.key} className="px-2 py-1">
                  {row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Tooltip box for every chart: the day, then each series with its colour swatch and value. */
export function ChartTooltip({ active, payload, label, labelFormatter, valueFormatter }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
      {label !== undefined && (
        <p className="mb-1 font-medium text-slate-900">
          {labelFormatter ? labelFormatter(label) : label}
        </p>
      )}
      {payload.map((entry) => (
        <p key={entry.dataKey ?? entry.name} className="flex items-center gap-2 text-slate-600">
          <span
            className="size-2 rounded-sm"
            style={{ background: entry.color || entry.payload?.fill }}
          />
          {entry.name}
          <span className="ml-auto pl-3 font-medium text-slate-900">
            {valueFormatter ? valueFormatter(entry.value) : entry.value}
          </span>
        </p>
      ))}
    </div>
  );
}

const PRESETS = [
  { days: 7, label: 'Last 7 days' },
  { days: 30, label: 'Last 30 days' },
  { days: 90, label: 'Last 90 days' },
];

/** Date range: presets or a custom from/to. Calls onChange({ from, to }). */
export function DateRangeFilter({ range, onChange }) {
  const [mode, setMode] = useState(String(range.preset ?? 'custom'));
  const [from, setFrom] = useState(range.from);
  const [to, setTo] = useState(range.to);

  function choose(value) {
    setMode(value);
    if (value !== 'custom') onChange(presetRange(Number(value)));
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <label className="relative">
        <span className="sr-only">Date range</span>
        <CalendarDays className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
        <select
          value={mode}
          onChange={(e) => choose(e.target.value)}
          className="rounded-lg border border-slate-300 bg-white py-2 pr-8 pl-9 text-sm"
        >
          {PRESETS.map((p) => (
            <option key={p.days} value={p.days}>
              {p.label}
            </option>
          ))}
          <option value="custom">Custom range…</option>
        </select>
      </label>
      {mode === 'custom' && (
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            onChange({ from, to, preset: null });
          }}
        >
          <input
            type="date"
            value={from}
            max={to}
            onChange={(e) => setFrom(e.target.value)}
            aria-label="From"
            className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
          />
          <span className="text-slate-400">–</span>
          <input
            type="date"
            value={to}
            min={from}
            max={isoDay(new Date())}
            onChange={(e) => setTo(e.target.value)}
            aria-label="To"
            className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
          />
          <Button type="submit" variant="secondary">
            Apply
          </Button>
        </form>
      )}
    </div>
  );
}
