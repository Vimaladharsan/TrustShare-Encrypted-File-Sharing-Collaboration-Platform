import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

import { OTHER, SERIES, SURFACE } from '../../utils/charts';
import { formatBytes } from '../../utils/format';
import { ChartCard, ChartTooltip } from '../analytics/AnalyticsParts';

const TOP_USERS = 6;

/** Pie: storage used by each user (largest 6, the rest grouped as "Others"). */
export function StorageByUserChart({ users }) {
  const top = users.slice(0, TOP_USERS).map((u, i) => ({
    name: u.full_name || u.email || 'Deleted account',
    value: u.bytes + u.vault_bytes,
    color: SERIES[i % SERIES.length],
  }));
  const rest = users.slice(TOP_USERS).reduce((n, u) => n + u.bytes + u.vault_bytes, 0);
  if (rest) top.push({ name: 'Others', value: rest, color: OTHER });
  const data = top.filter((d) => d.value > 0);
  return (
    <ChartCard
      title="Storage by user"
      legend={data.map((d) => ({
        key: d.name,
        label: d.name,
        color: d.color,
        value: formatBytes(d.value),
      }))}
      empty={data.length === 0}
      emptyText="No files stored yet."
      table={{
        columns: [
          { key: 'name', label: 'User' },
          { key: 'size', label: 'Stored' },
        ],
        rows: data.map((d) => ({ name: d.name, size: formatBytes(d.value) })),
      }}
    >
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius="55%"
              outerRadius="85%"
              paddingAngle={2}
              stroke={SURFACE}
              strokeWidth={2}
              isAnimationActive={false}
            >
              {data.map((d) => (
                <Cell key={d.name} fill={d.color} />
              ))}
            </Pie>
            <Tooltip content={<ChartTooltip valueFormatter={formatBytes} />} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  );
}
