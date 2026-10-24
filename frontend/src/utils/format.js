import { File, FileImage, FileSpreadsheet, FileText, Presentation } from 'lucide-react';

/** 482133 → "471 KB" */
export function formatBytes(bytes) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** exponent;
  return `${value >= 10 || exponent === 0 ? Math.round(value) : value.toFixed(1)} ${units[exponent]}`;
}

/** ISO date → "12 Oct 2026" */
export function formatDate(iso) {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

export const CATEGORIES = [
  { value: '', label: 'All' },
  { value: 'document', label: 'Documents' },
  { value: 'spreadsheet', label: 'Spreadsheets' },
  { value: 'presentation', label: 'Presentations' },
  { value: 'image', label: 'Images' },
  { value: 'text', label: 'Text' },
];

const ICONS = {
  document: { Icon: FileText, color: 'text-red-500', tile: 'bg-red-50 text-red-600 ring-red-100' },
  spreadsheet: {
    Icon: FileSpreadsheet,
    color: 'text-green-600',
    tile: 'bg-emerald-50 text-emerald-600 ring-emerald-100',
  },
  presentation: {
    Icon: Presentation,
    color: 'text-orange-500',
    tile: 'bg-orange-50 text-orange-600 ring-orange-100',
  },
  image: {
    Icon: FileImage,
    color: 'text-purple-500',
    tile: 'bg-violet-50 text-violet-600 ring-violet-100',
  },
  text: { Icon: File, color: 'text-slate-500', tile: 'bg-slate-100 text-slate-500 ring-slate-200' },
};

export function fileIcon(category) {
  return ICONS[category] || ICONS.text;
}
