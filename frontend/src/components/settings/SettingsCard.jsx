/** A settings section: title and short description on top, content below. */
export default function SettingsCard({ title, description, action, children, tone = 'default' }) {
  const danger = tone === 'danger';
  return (
    <section className={`card overflow-hidden ${danger ? '!border-red-200' : ''}`}>
      <div
        className={`flex flex-wrap items-start justify-between gap-3 border-b px-5 py-4 sm:px-6 ${
          danger ? 'border-red-100 bg-red-50/50' : 'border-slate-100'
        }`}
      >
        <div>
          <h2 className={`font-semibold ${danger ? 'text-red-700' : 'text-slate-950'}`}>{title}</h2>
          {description && <p className="mt-0.5 text-sm text-slate-500">{description}</p>}
        </div>
        {action}
      </div>
      <div className="px-5 py-5 sm:px-6">{children}</div>
    </section>
  );
}
