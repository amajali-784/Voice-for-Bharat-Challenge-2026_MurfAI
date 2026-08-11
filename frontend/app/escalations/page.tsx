'use client';

import { useCallback, useEffect, useState } from 'react';

type EscalationRequest = {
  reference_id: string;
  caller_id: string;
  caller_name: string | null;
  category: string;
  urgency: 'low' | 'medium' | 'high' | 'emergency';
  summary: string;
  checked: string;
  followup: string;
  language: string;
  status: 'open' | 'in_progress' | 'resolved';
  created_at: string;
  updated_at: string;
};

const ESCALATION_API_URL = process.env.NEXT_PUBLIC_ESCALATION_API_URL ?? 'http://localhost:8701';

const STATUS_LABELS: Record<EscalationRequest['status'], string> = {
  open: 'Open · खुला',
  in_progress: 'In progress · कार्य जारी',
  resolved: 'Resolved · हल हो गया',
};

const URGENCY_STYLES: Record<EscalationRequest['urgency'], string> = {
  emergency: 'bg-red-600/15 text-red-700 dark:text-red-300 border-red-500/40',
  high: 'bg-orange-500/15 text-orange-700 dark:text-orange-300 border-orange-500/40',
  medium: 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/40',
  low: 'bg-sage/15 text-forest dark:text-sage-light border-sage/40',
};

const CATEGORY_LABELS: Record<string, string> = {
  red_flag_symptom: 'Red-flag symptom · गंभीर लक्षण',
  diagnosis_request: 'Diagnosis request · निदान की माँग',
};

function formatDate(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
}

function Field({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <div className="flex flex-col gap-1">
      <span className="text-muted-foreground text-[11px] font-bold tracking-wider uppercase">
        {label}
      </span>
      <p className="text-foreground text-sm">{value}</p>
    </div>
  );
}

export default function EscalationsPage() {
  const [requests, setRequests] = useState<EscalationRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | EscalationRequest['status']>('all');

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${ESCALATION_API_URL}/escalations`);
      if (!res.ok) throw new Error(`Escalation API returned ${res.status}`);
      const data = await res.json();
      setRequests(data.requests ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const setStatus = async (referenceId: string, status: EscalationRequest['status']) => {
    try {
      const res = await fetch(
        `${ESCALATION_API_URL}/escalations/${encodeURIComponent(referenceId)}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status }),
        }
      );
      if (!res.ok) throw new Error(`Escalation API returned ${res.status}`);
      const updated = (await res.json()) as EscalationRequest;
      setRequests((prev) => prev.map((r) => (r.reference_id === referenceId ? updated : r)));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const visible = filter === 'all' ? requests : requests.filter((r) => r.status === filter);
  const openCount = requests.filter((r) => r.status === 'open').length;

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-4 pt-28 pb-20 md:px-8">
      <div className="flex flex-col gap-2">
        <h1
          className="text-foreground text-2xl font-bold md:text-3xl"
          style={{ fontFamily: 'var(--font-mukta)' }}
        >
          मानव सहायता अनुरोध (Human Help Requests)
        </h1>
        <p className="text-muted-foreground text-sm">
          ये वे कॉल हैं जहाँ एजेंट ने कॉलर की अनुमति के साथ किसी इंसान की मदद माँगी है — गंभीर लक्षण
          या निदान की माँग। गोपनीय जानकारी (फ़ोन नंबर, OTP, खाता नंबर) कभी यहाँ नहीं भेजी जाती। API:{' '}
          <code className="font-mono text-xs">{ESCALATION_API_URL}</code>
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-sm">
          {openCount > 0 && (
            <span className="bg-forest text-forest dark:bg-sage dark:text-sage-light rounded-full px-3 py-1 text-xs font-bold">
              {openCount} open request{openCount === 1 ? '' : 's'}
            </span>
          )}
          <span className="flex gap-1.5">
            {(['all', 'open', 'in_progress', 'resolved'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`rounded-full border px-3 py-1 text-xs font-semibold transition-colors ${
                  filter === f
                    ? 'bg-forest text-forest border-forest dark:bg-sage dark:text-sage-light dark:border-sage'
                    : 'border-border text-muted-foreground hover:bg-card'
                }`}
              >
                {f === 'all'
                  ? 'All'
                  : f === 'open'
                    ? 'Open'
                    : f === 'in_progress'
                      ? 'In progress'
                      : 'Resolved'}
              </button>
            ))}
          </span>
        </div>
      </div>

      {error && (
        <div className="border-border bg-card/70 border p-4 text-sm text-red-600 dark:text-red-400">
          Could not reach the escalation API: {error}. Make sure it is running (
          <code className="font-mono">uv run python src/escalation_api.py</code>).
        </div>
      )}

      {loading && <p className="text-muted-foreground text-sm">Loading…</p>}

      {!loading && !error && visible.length === 0 && (
        <div className="border-border bg-card/70 border p-8 text-center">
          <p className="text-muted-foreground text-sm">
            No human-help requests here yet. The agent files one only when a caller reports a
            red-flag symptom or asks for a diagnosis — and only after the caller says yes.
          </p>
        </div>
      )}

      <div className="flex flex-col gap-4">
        {visible.map((req) => (
          <div key={req.reference_id} className="border-border bg-card/70 rounded-2xl border p-5">
            <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-foreground text-lg font-bold">
                    {req.caller_name ?? 'Unknown caller'}
                  </h2>
                  <span
                    className={`rounded-full border px-2.5 py-0.5 text-[11px] font-bold ${
                      URGENCY_STYLES[req.urgency] ?? URGENCY_STYLES.medium
                    }`}
                  >
                    {req.urgency}
                  </span>
                  <span className="text-muted-foreground border-border rounded-full border px-2.5 py-0.5 text-[11px] font-semibold">
                    {STATUS_LABELS[req.status]}
                  </span>
                </div>
                <p className="text-muted-foreground font-mono text-[11px]">{req.reference_id}</p>
                <p className="text-muted-foreground mt-1 text-xs">
                  {CATEGORY_LABELS[req.category] ?? req.category} · Created{' '}
                  {formatDate(req.created_at)}
                </p>
              </div>

              <div className="flex flex-col items-end gap-2">
                <span className="text-muted-foreground font-mono text-[10px] break-all">
                  {req.caller_id}
                </span>
                {req.status !== 'resolved' && (
                  <div className="flex gap-2">
                    {req.status === 'open' && (
                      <button
                        onClick={() => void setStatus(req.reference_id, 'in_progress')}
                        className="border-forest/40 text-forest hover:bg-forest/10 dark:border-sage/40 dark:text-sage-light dark:hover:bg-sage/10 rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors"
                      >
                        Start working
                      </button>
                    )}
                    <button
                      onClick={() => void setStatus(req.reference_id, 'resolved')}
                      className="rounded-full border border-green-500/40 px-3 py-1.5 text-xs font-semibold text-green-700 transition-colors hover:bg-green-500/10 dark:text-green-400"
                    >
                      Mark resolved
                    </button>
                  </div>
                )}
              </div>
            </div>

            <div className="flex flex-col gap-3">
              <Field label="What happened · क्या हुआ" value={req.summary} />
              <Field label="Already checked · एजेंट ने क्या जाँचा" value={req.checked} />
              <Field label="Preferred follow-up" value={req.followup} />
              <Field label="Language" value={req.language} />
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
