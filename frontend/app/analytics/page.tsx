'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

type Outcome = 'success' | 'failed';

type Summary = {
  total: number;
  success: number;
  failed: number;
  success_rate: number | null;
  avg_duration_seconds: number | null;
  avg_latency_ms: number | null;
  today: { date: string; total: number; success: number; failed: number };
  by_channel: Record<string, { total: number; success: number; failed: number }>;
  by_failure: Record<string, number>;
  by_reason: Record<string, number>;
};

type DailyPoint = { date: string; total: number; success: number; failed: number };
type LatencyPoint = { date: string; avg_ms: number | null };

type RecentCall = {
  call_id: string;
  caller_id: string;
  channel: string;
  outcome: Outcome;
  failure_type: string | null;
  reason: string | null;
  started_at: string;
  duration_seconds: number | null;
  user_turns: number;
  agent_turns: number;
  tools_used: string[];
  escalation_created: boolean;
  facility_delivered: boolean;
  avg_latency_ms: number | null;
  error: string | null;
};

type AnalyticsPayload = {
  summary: Summary;
  daily: DailyPoint[];
  latency_trend: LatencyPoint[];
  recent_calls: RecentCall[];
};

const ANALYTICS_API_URL = process.env.NEXT_PUBLIC_ANALYTICS_API_URL ?? 'http://localhost:8702';

const CHANNEL_LABELS: Record<string, string> = {
  browser: 'Browser',
  sip: 'SIP',
  console: 'Console',
  eval: 'Eval',
};

const FAILURE_LABELS: Record<string, string> = {
  no_response: 'No response',
  user_hangup: 'User hung up',
  incomplete: 'Incomplete',
  tool_error: 'Tool / API error',
  sip_no_answer: 'SIP — no answer',
  sip_busy: 'SIP — busy',
  sip_declined: 'SIP — declined',
  sip_trunk_failure: 'SIP — trunk failure',
  sip_voicemail: 'SIP — voicemail',
  sip_hung_up_immediate: 'SIP — hung up early',
  sip_opted_out: 'SIP — opted out',
  sip_unknown: 'SIP — unknown',
};

function formatDate(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
}

function StatCard({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string | number;
  sub?: string;
  tone: 'neutral' | 'good' | 'bad';
}) {
  const toneStyles = {
    neutral: 'border-border bg-card/70',
    good: 'border-green-500/30 bg-green-500/5',
    bad: 'border-red-500/30 bg-red-500/5',
  }[tone];
  const valueStyles = {
    neutral: 'text-foreground',
    good: 'text-green-700 dark:text-green-400',
    bad: 'text-red-600 dark:text-red-400',
  }[tone];

  return (
    <div className={`${toneStyles} flex flex-col gap-1 rounded-2xl border p-5`}>
      <span className="text-muted-foreground text-[11px] font-bold tracking-wider uppercase">
        {label}
      </span>
      <span
        className={`${valueStyles} text-4xl font-bold tabular-nums`}
        style={{ fontFamily: 'var(--font-mukta)' }}
      >
        {value}
      </span>
      {sub && <span className="text-muted-foreground text-xs">{sub}</span>}
    </div>
  );
}

function DailyChart({ daily }: { daily: DailyPoint[] }) {
  const max = Math.max(1, ...daily.map((d) => d.total));
  return (
    <div className="border-border bg-card/70 rounded-2xl border p-5">
      <h2
        className="text-foreground mb-4 text-lg font-bold"
        style={{ fontFamily: 'var(--font-mukta)' }}
      >
        Calls over time · पिछले दिन
      </h2>
      <div className="flex h-40 items-end gap-1.5">
        {daily.map((d) => (
          <div
            key={d.date}
            className="group flex h-full flex-1 flex-col justify-end"
            title={`${d.date}`}
          >
            <div className="flex h-full flex-col justify-end rounded-t">
              {d.success > 0 && (
                <div
                  className="bg-sage w-full transition-all"
                  style={{ height: `${(d.success / max) * 100}%` }}
                />
              )}
              {d.failed > 0 && (
                <div
                  className="w-full bg-red-400/70 transition-all"
                  style={{ height: `${(d.failed / max) * 100}%` }}
                />
              )}
            </div>
          </div>
        ))}
      </div>
      <div className="text-muted-foreground mt-3 flex items-center gap-4 text-[11px] font-semibold">
        <span className="flex items-center gap-1.5">
          <span className="bg-sage inline-block size-2.5 rounded-sm" /> Successful
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-sm bg-red-400/70" /> Failed
        </span>
        <span className="text-muted-foreground ml-auto">
          {daily[0]?.date} → {daily[daily.length - 1]?.date}
        </span>
      </div>
    </div>
  );
}

function RecentCalls({ calls }: { calls: RecentCall[] }) {
  if (calls.length === 0) {
    return (
      <div className="border-border bg-card/70 rounded-2xl border p-8 text-center">
        <p className="text-muted-foreground text-sm">
          No calls recorded yet. Start a call with the agent and its outcome will appear here
          automatically — no private details, just anonymised counts and timings.
        </p>
      </div>
    );
  }

  return (
    <div className="border-border bg-card/70 overflow-hidden rounded-2xl border">
      <div className="flex items-center justify-between px-5 pt-5 pb-3">
        <h2
          className="text-foreground text-lg font-bold"
          style={{ fontFamily: 'var(--font-mukta)' }}
        >
          Recent calls · हाल की कॉलें
        </h2>
        <span className="text-muted-foreground text-xs">Newest first</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="text-muted-foreground border-border border-b text-[11px] tracking-wider uppercase">
              <th className="px-5 py-2.5 font-bold">When</th>
              <th className="px-3 py-2.5 font-bold">Channel</th>
              <th className="px-3 py-2.5 font-bold">Duration</th>
              <th className="px-3 py-2.5 font-bold">Outcome</th>
              <th className="px-3 py-2.5 font-bold">Why</th>
            </tr>
          </thead>
          <tbody>
            {calls.map((call) => (
              <tr key={call.call_id} className="border-border border-b last:border-0">
                <td className="text-muted-foreground px-5 py-3 whitespace-nowrap">
                  {formatDate(call.started_at)}
                </td>
                <td className="px-3 py-3">
                  <span className="border-border text-muted-foreground rounded-full border px-2 py-0.5 font-mono text-[10px] font-bold uppercase">
                    {CHANNEL_LABELS[call.channel] ?? call.channel}
                  </span>
                </td>
                <td className="text-foreground px-3 py-3 tabular-nums">
                  {formatDuration(call.duration_seconds)}
                </td>
                <td className="px-3 py-3">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold ${
                      call.outcome === 'success'
                        ? 'bg-green-500/15 text-green-700 dark:text-green-400'
                        : 'bg-red-500/15 text-red-600 dark:text-red-400'
                    }`}
                  >
                    {call.outcome === 'success' ? 'Successful' : 'Failed'}
                  </span>
                </td>
                <td className="text-muted-foreground px-3 py-3">
                  {call.outcome === 'failed'
                    ? (FAILURE_LABELS[call.failure_type ?? ''] ?? call.failure_type ?? 'Unknown')
                    : (call.reason ?? '—')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const res = await fetch(`${ANALYTICS_API_URL}/analytics`);
      if (!res.ok) throw new Error(`Analytics API returned ${res.status}`);
      const payload = (await res.json()) as AnalyticsPayload;
      setData(payload);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (live) {
      timerRef.current = setInterval(() => void refresh(), 5000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [live, refresh]);

  const summary = data?.summary;
  const failureBreakdown = summary
    ? Object.entries(summary.by_failure)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 6)
    : [];

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-8 px-4 pt-28 pb-20 md:px-8">
      <div className="flex flex-col gap-2">
        <h1
          className="text-foreground text-2xl font-bold md:text-3xl"
          style={{ fontFamily: 'var(--font-mukta)' }}
        >
          कॉल विश्लेषण (Call Analytics)
        </h1>
        <p className="text-muted-foreground text-sm">
          आपके वॉइस एजेंट के हर कॉल का परिणाम — कुल, सफल और असफल। ये संख्याएँ वास्तविक कॉल से आती
          हैं। कोई निजी जानकारी (नाम, फ़ोन, OTP, ट्रांसक्रिप्ट) यहाँ नहीं दिखाई जाती। API:{' '}
          <code className="font-mono text-xs">{ANALYTICS_API_URL}</code>
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
          <button
            onClick={() => setLive((v) => !v)}
            className={`rounded-full border px-3 py-1 font-semibold transition-colors ${
              live
                ? 'bg-forest text-forest border-forest dark:bg-sage dark:text-sage-light dark:border-sage'
                : 'border-border text-muted-foreground hover:bg-card'
            }`}
          >
            {live ? '● Live updates on' : 'Live updates off'}
          </button>
          <button
            onClick={() => void refresh()}
            className="border-border text-muted-foreground hover:bg-card rounded-full border px-3 py-1 font-semibold transition-colors"
          >
            Refresh now
          </button>
          {lastUpdated && (
            <span className="text-muted-foreground">
              Updated {lastUpdated.toLocaleTimeString('en-IN')}
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="border-border bg-card/70 border p-4 text-sm text-red-600 dark:text-red-400">
          Could not reach the analytics API: {error}. Make sure it is running (
          <code className="font-mono">uv run python src/analytics_api.py</code>).
        </div>
      )}

      {loading && <p className="text-muted-foreground text-sm">Loading…</p>}

      {!loading && !error && summary && (
        <>
          <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCard
              label="Total calls · कुल कॉल"
              value={summary.total}
              tone="neutral"
              sub="All browser, SIP and test calls"
            />
            <StatCard
              label="Successful · सफल"
              value={summary.success}
              tone="good"
              sub={
                summary.success_rate != null
                  ? `Success rate ${summary.success_rate}%`
                  : 'No calls yet'
              }
            />
            <StatCard
              label="Failed · असफल"
              value={summary.failed}
              tone="bad"
              sub="Did not reach the success condition"
            />
          </section>

          <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="border-border bg-card/70 rounded-2xl border p-5">
              <span className="text-muted-foreground text-[11px] font-bold tracking-wider uppercase">
                Today · आज
              </span>
              <div className="mt-2 flex flex-col gap-1 text-sm">
                <span className="text-foreground">
                  {summary.today.total} total ·{' '}
                  <span className="text-green-700 dark:text-green-400">
                    {summary.today.success} success
                  </span>{' '}
                  ·{' '}
                  <span className="text-red-600 dark:text-red-400">
                    {summary.today.failed} failed
                  </span>
                </span>
                <span className="text-muted-foreground text-xs">{summary.today.date}</span>
              </div>
            </div>
            <div className="border-border bg-card/70 rounded-2xl border p-5">
              <span className="text-muted-foreground text-[11px] font-bold tracking-wider uppercase">
                Avg duration
              </span>
              <div className="text-foreground mt-2 text-2xl font-bold tabular-nums">
                {summary.avg_duration_seconds != null
                  ? formatDuration(summary.avg_duration_seconds)
                  : '—'}
              </div>
            </div>
            <div className="border-border bg-card/70 rounded-2xl border p-5">
              <span className="text-muted-foreground text-[11px] font-bold tracking-wider uppercase">
                First reply latency
              </span>
              <div className="text-foreground mt-2 text-2xl font-bold tabular-nums">
                {summary.avg_latency_ms != null ? `${Math.round(summary.avg_latency_ms)}ms` : '—'}
              </div>
            </div>
          </section>

          <DailyChart daily={data.daily} />

          <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="border-border bg-card/70 rounded-2xl border p-5">
              <h2
                className="text-foreground mb-3 text-lg font-bold"
                style={{ fontFamily: 'var(--font-mukta)' }}
              >
                By channel · चैनल
              </h2>
              {Object.keys(summary.by_channel).length === 0 ? (
                <p className="text-muted-foreground text-sm">No calls yet.</p>
              ) : (
                <div className="flex flex-col gap-2.5">
                  {Object.entries(summary.by_channel).map(([channel, counts]) => (
                    <div key={channel} className="flex items-center gap-3 text-sm">
                      <span className="text-muted-foreground w-20 font-semibold">
                        {CHANNEL_LABELS[channel] ?? channel}
                      </span>
                      <div className="flex h-4 flex-1 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
                        {counts.total > 0 && (
                          <>
                            <div
                              className="bg-sage h-full"
                              style={{ width: `${(counts.success / counts.total) * 100}%` }}
                            />
                            <div
                              className="h-full bg-red-400/70"
                              style={{ width: `${(counts.failed / counts.total) * 100}%` }}
                            />
                          </>
                        )}
                      </div>
                      <span className="text-muted-foreground w-24 text-right tabular-nums">
                        {counts.success} / {counts.total}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="border-border bg-card/70 rounded-2xl border p-5">
              <h2
                className="text-foreground mb-3 text-lg font-bold"
                style={{ fontFamily: 'var(--font-mukta)' }}
              >
                Why calls failed · असफल क्यों
              </h2>
              {failureBreakdown.length === 0 ? (
                <p className="text-muted-foreground text-sm">No failures yet.</p>
              ) : (
                <div className="flex flex-col gap-2.5">
                  {failureBreakdown.map(([type, count]) => (
                    <div key={type} className="flex items-center gap-3 text-sm">
                      <span className="text-muted-foreground flex-1">
                        {FAILURE_LABELS[type] ?? type}
                      </span>
                      <span className="text-foreground font-bold tabular-nums">{count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          <RecentCalls calls={data.recent_calls} />
        </>
      )}
    </main>
  );
}
