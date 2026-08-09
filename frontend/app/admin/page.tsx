'use client';

import { useCallback, useEffect, useState } from 'react';

type CallerProfile = {
  caller_id: string;
  name: string | null;
  language: string | null;
  location: string | null;
  phone: string | null;
  dob: string | null;
  gender: string | null;
  conditions: string[];
  medications: string[];
  allergies: string[];
  notes: string[];
  last_called_at: string | null;
  created_at: string;
};

const MEMORY_API_URL = process.env.NEXT_PUBLIC_MEMORY_API_URL ?? 'http://localhost:8700';

function formatDate(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
}

function Chips({ label, items }: { label: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="flex flex-col gap-1">
      <span className="text-muted-foreground text-[11px] font-bold tracking-wider uppercase">
        {label}
      </span>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <span
            key={item}
            className="bg-forest/10 text-forest dark:bg-sage/10 dark:text-sage-light rounded-full px-2.5 py-0.5 text-xs"
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function AdminPage() {
  const [callers, setCallers] = useState<CallerProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${MEMORY_API_URL}/callers`);
      if (!res.ok) throw new Error(`Memory API returned ${res.status}`);
      const data = await res.json();
      setCallers(data.callers ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const forgetCaller = async (callerId: string) => {
    try {
      const res = await fetch(`${MEMORY_API_URL}/callers/${encodeURIComponent(callerId)}`, {
        method: 'DELETE',
      });
      if (!res.ok) throw new Error(`Memory API returned ${res.status}`);
      setCallers((prev) => prev.filter((c) => c.caller_id !== callerId));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-4 pt-28 pb-20 md:px-8">
      <div className="flex flex-col gap-2">
        <h1
          className="text-foreground text-2xl font-bold md:text-3xl"
          style={{ fontFamily: 'var(--font-mukta)' }}
        >
          याद किए गए कॉलर (Remembered Callers)
        </h1>
        <p className="text-muted-foreground text-sm">
          आपका वॉइस एजेंट इन कॉलर की जानकारी याद रखता है। अपनी पहचान भूलने पर यहाँ से हटा सकते हैं।
          API: <code className="font-mono text-xs">{MEMORY_API_URL}</code>
        </p>
      </div>

      {error && (
        <div className="border-border bg-card/70 border p-4 text-sm text-red-600 dark:text-red-400">
          Could not reach the memory API: {error}. Make sure the backend admin server is running (
          <code className="font-mono">uv run python src/memory_api.py</code>).
        </div>
      )}

      {loading && <p className="text-muted-foreground text-sm">Loading…</p>}

      {!loading && !error && callers.length === 0 && (
        <div className="border-border bg-card/70 border p-8 text-center">
          <p className="text-muted-foreground text-sm">No remembered callers yet.</p>
        </div>
      )}

      <div className="flex flex-col gap-4">
        {callers.map((caller) => (
          <div key={caller.caller_id} className="border-border bg-card/70 rounded-2xl border p-5">
            <div className="mb-3 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-foreground text-lg font-bold">
                  {caller.name ?? 'Unknown caller'}
                </h2>
                <p className="text-muted-foreground font-mono text-[11px] break-all">
                  {caller.caller_id}
                </p>
                <p className="text-muted-foreground mt-1 text-xs">
                  Last called {formatDate(caller.last_called_at)} · Since{' '}
                  {formatDate(caller.created_at)}
                </p>
              </div>
              <button
                onClick={() => void forgetCaller(caller.caller_id)}
                className="rounded-full border border-red-500/40 px-3 py-1.5 text-xs font-semibold text-red-600 transition-colors hover:bg-red-500/10 dark:text-red-400"
              >
                Forget
              </button>
            </div>

            {(caller.location ||
              caller.language ||
              caller.gender ||
              caller.dob ||
              caller.phone) && (
              <dl className="mb-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
                {caller.language && (
                  <>
                    <dt className="text-muted-foreground text-[11px] font-bold tracking-wider uppercase">
                      Language
                    </dt>
                    <dd>{caller.language}</dd>
                  </>
                )}
                {caller.location && (
                  <>
                    <dt className="text-muted-foreground text-[11px] font-bold tracking-wider uppercase">
                      Location
                    </dt>
                    <dd>{caller.location}</dd>
                  </>
                )}
                {caller.gender && (
                  <>
                    <dt className="text-muted-foreground text-[11px] font-bold tracking-wider uppercase">
                      Gender
                    </dt>
                    <dd>{caller.gender}</dd>
                  </>
                )}
                {caller.dob && (
                  <>
                    <dt className="text-muted-foreground text-[11px] font-bold tracking-wider uppercase">
                      Age / DOB
                    </dt>
                    <dd>{caller.dob}</dd>
                  </>
                )}
                {caller.phone && (
                  <>
                    <dt className="text-muted-foreground text-[11px] font-bold tracking-wider uppercase">
                      Phone
                    </dt>
                    <dd>{caller.phone}</dd>
                  </>
                )}
              </dl>
            )}

            <div className="flex flex-col gap-2">
              <Chips label="Conditions" items={caller.conditions} />
              <Chips label="Medications" items={caller.medications} />
              <Chips label="Allergies" items={caller.allergies} />
              {caller.notes.length > 0 && (
                <div className="flex flex-col gap-1">
                  <span className="text-muted-foreground text-[11px] font-bold tracking-wider uppercase">
                    Notes
                  </span>
                  <ul className="text-muted-foreground list-inside list-disc text-sm">
                    {caller.notes.map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
