import { BadgeCheck, FolderOpen, Search, ShieldCheck, Trash2, Upload } from 'lucide-react';

import { fileIcon } from '../../utils/format';

const ROWS = [
  { name: 'Project plan.pdf', size: '2.4 MB', date: 'Today', category: 'document' },
  { name: 'Budget 2026.xlsx', size: '820 KB', date: 'Today', category: 'spreadsheet' },
  { name: 'Pitch deck.pptx', size: '5.1 MB', date: 'Yesterday', category: 'presentation' },
  { name: 'Site photo.png', size: '3.2 MB', date: '12 Oct', category: 'image' },
];

/** Decorative dashboard mock-up for the landing page hero (HTML, so it's sharp at any size). */
export default function ProductPreview() {
  return (
    <div className="relative" aria-hidden="true">
      <div className="absolute -inset-6 -z-10 rounded-[2rem] bg-gradient-to-br from-blue-200/60 via-indigo-100/40 to-cyan-100/60 blur-2xl" />

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl shadow-blue-900/10">
        {/* window bar */}
        <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-3">
          <span className="size-2.5 rounded-full bg-red-300" />
          <span className="size-2.5 rounded-full bg-amber-300" />
          <span className="size-2.5 rounded-full bg-green-300" />
          <div className="ml-3 flex flex-1 items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-400">
            <Search className="size-3" /> Search files
          </div>
        </div>

        <div className="flex">
          {/* sidebar */}
          <div className="hidden w-36 shrink-0 flex-col gap-1 border-r border-slate-100 p-3 text-xs sm:flex">
            <span className="flex items-center gap-2 rounded-md bg-blue-50 px-2 py-1.5 font-medium text-blue-700">
              <FolderOpen className="size-3.5" /> My Files
            </span>
            <span className="flex items-center gap-2 px-2 py-1.5 text-slate-500">
              <Trash2 className="size-3.5" /> Trash
            </span>
            <div className="mt-auto pt-10">
              <div className="h-1.5 rounded-full bg-slate-100">
                <div className="h-1.5 w-1/3 rounded-full bg-blue-500" />
              </div>
              <p className="mt-1 text-[10px] text-slate-400">340 MB of 1 GB</p>
            </div>
          </div>

          {/* file list */}
          <div className="flex-1 p-4">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm font-semibold text-slate-800">My Files</p>
              <span className="flex items-center gap-1 rounded-md bg-blue-600 px-2 py-1 text-[11px] font-medium text-white">
                <Upload className="size-3" /> Upload
              </span>
            </div>
            <ul className="divide-y divide-slate-100 text-xs">
              {ROWS.map((row) => {
                const { Icon, color } = fileIcon(row.category);
                return (
                  <li key={row.name} className="flex items-center gap-3 py-2">
                    <Icon className={`size-4 shrink-0 ${color}`} />
                    <span className="flex-1 truncate text-slate-700">{row.name}</span>
                    <span className="hidden w-16 text-right text-slate-400 sm:block">
                      {row.size}
                    </span>
                    <span className="w-16 text-right text-slate-400">{row.date}</span>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      </div>

      {/* floating badges */}
      <div className="absolute -bottom-5 -left-4 flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg sm:-left-8">
        <BadgeCheck className="size-4 text-emerald-500" />
        <span>
          <span className="block font-medium text-slate-800">Content verified</span>
          <span className="block text-slate-400">Real PDF · SHA-256 saved</span>
        </span>
      </div>
      <div className="absolute -top-4 -right-3 flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg sm:-right-6">
        <ShieldCheck className="size-4 text-blue-600" />
        <span className="font-medium text-slate-800">2-step verification on</span>
      </div>
    </div>
  );
}
