// Chart colours and labels – one fixed colour per meaning, in a validated, colour-blind-safe
// order (checked with a palette validator: lightness, chroma, CVD separation). The same entity
// always keeps its colour, on every chart and after any filter.

export const SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4'];

export const CATEGORY_SERIES = [
  { key: 'document', label: 'Documents', color: SERIES[0] },
  { key: 'spreadsheet', label: 'Spreadsheets', color: SERIES[1] },
  { key: 'presentation', label: 'Presentations', color: SERIES[2] },
  { key: 'image', label: 'Images', color: SERIES[3] },
  { key: 'text', label: 'Text', color: SERIES[4] },
];

export const DOWNLOAD_SERIES = [
  { key: 'total', label: 'Total downloads', color: SERIES[0] },
  { key: 'unique_users', label: 'Unique users', color: SERIES[1] },
  { key: 'shared', label: 'Shared-file downloads', color: SERIES[2] },
];

export const SHARE_SERIES = [
  { key: 'link', label: 'Link shares', color: SERIES[0] },
  { key: 'direct', label: 'Direct shares (people)', color: SERIES[1] },
];

// Recessive chart chrome (grid, axes) – text uses ink colours, never series colours.
export const GRID = '#e2e8f0';
export const AXIS_TEXT = '#64748b';

/** '2026-10-05' → '5 Oct' (axis ticks) */
export function shortDay(iso) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
  });
}

/** YYYY-MM-DD in the browser's local time zone. */
export function isoDay(date) {
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}

/** "+12%" / "−5%" / "New" / "0%" – change vs the previous period of the same length. */
export function changeLabel({ value, previous }) {
  if (previous === 0) return value === 0 ? '0%' : 'New';
  const percent = Math.round(((value - previous) / previous) * 100);
  return `${percent > 0 ? '+' : percent < 0 ? '−' : ''}${Math.abs(percent)}%`;
}

/** The last `days` days up to today: { from, to, preset }. */
export function presetRange(days) {
  const to = new Date();
  const from = new Date();
  from.setDate(to.getDate() - (days - 1));
  return { from: isoDay(from), to: isoDay(to), preset: days };
}
