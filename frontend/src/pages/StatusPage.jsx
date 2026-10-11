import { useEffect, useState } from 'react';

import { api } from '../api/client';

const SERVICES = [
  { key: 'postgres', name: 'PostgreSQL', role: 'Users, roles & permissions' },
  { key: 'mongodb', name: 'MongoDB', role: 'File metadata & activity logs' },
  { key: 'redis', name: 'Redis', role: 'Sessions, tokens & rate limits' },
];

// Shows that the frontend can reach the backend, and the backend can reach all 3 databases.
export default function StatusPage() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setError('');
    try {
      const { data } = await api.get('/health');
      setHealth(data);
    } catch (err) {
      // A 503 still has a body saying which service is down.
      if (err.response?.data?.services) setHealth(err.response.data);
      else setError('Cannot reach the backend. Is it running?');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <main className="mx-auto max-w-xl px-4 py-16">
      <h1 className="text-3xl font-bold text-blue-700">TrustShare</h1>
      <p className="mt-1 text-slate-500">Secure file sharing</p>

      <section className="mt-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">System status</h2>
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="rounded-lg border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50 disabled:opacity-50"
          >
            {loading ? 'Checking…' : 'Refresh'}
          </button>
        </div>

        {error && (
          <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
        )}

        <ul className="mt-4 divide-y divide-slate-100">
          {SERVICES.map(({ key, name, role }) => {
            const status = health?.services?.[key];
            return (
              <li key={key} className="flex items-center justify-between py-3">
                <div>
                  <p className="font-medium">{name}</p>
                  <p className="text-sm text-slate-500">{role}</p>
                </div>
                <span
                  className={`rounded-full px-3 py-1 text-sm font-medium ${
                    status === 'ok'
                      ? 'bg-green-100 text-green-700'
                      : status === 'error'
                        ? 'bg-red-100 text-red-700'
                        : 'bg-slate-100 text-slate-500'
                  }`}
                >
                  {status ?? '…'}
                </span>
              </li>
            );
          })}
        </ul>
      </section>
    </main>
  );
}
