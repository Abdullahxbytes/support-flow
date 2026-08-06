import React from 'react';
import { AnalyticsSummary } from '../../api/tickets';
import { WebSocketConnectionState } from '../../types/websocket';

interface DashboardLayoutProps {
  connectionState: WebSocketConnectionState;
  connectionError?: string | null;
  analytics?: AnalyticsSummary | null;
  queueMetrics?: {
    activeTickets: number;
    escalations: number;
    aiConfidence: number;
  };
  children?: React.ReactNode;
}

const statusStyles: Record<WebSocketConnectionState, string> = {
  CONNECTING: 'bg-amber-500',
  OPEN: 'bg-emerald-500',
  CLOSING: 'bg-slate-500',
  CLOSED: 'bg-rose-500',
};

const statusLabel: Record<WebSocketConnectionState, string> = {
  CONNECTING: 'Connecting',
  OPEN: 'Connected',
  CLOSING: 'Closing',
  CLOSED: 'Disconnected',
};

export function DashboardLayout({ connectionState, connectionError, analytics, queueMetrics, children }: DashboardLayoutProps) {
  const activeTickets = queueMetrics?.activeTickets ?? analytics?.total_triaged_count ?? 0;
  const escalations = queueMetrics?.escalations ?? 0;
  const confidenceScore = queueMetrics ? `${queueMetrics.aiConfidence.toFixed(1)}%` : analytics ? `${(analytics.average_rag_confidence * 100).toFixed(0)}%` : '0.0%';

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/90 px-6 py-4 backdrop-blur">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-slate-400">SupportFlow</p>
            <h1 className="text-2xl font-semibold">Agent Co-Pilot Dashboard</h1>
          </div>
          <div className="flex items-center gap-3 rounded-full border border-slate-700 bg-slate-800 px-4 py-2">
            <span className={`h-2.5 w-2.5 rounded-full ${statusStyles[connectionState]}`} />
            <span className="text-sm font-medium">{statusLabel[connectionState]}</span>
            {connectionError ? <span className="text-xs text-amber-400">{connectionError}</span> : null}
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-7xl flex-col gap-6 px-6 py-6 lg:flex-row">
        <aside className="w-full max-w-sm rounded-2xl border border-slate-800 bg-slate-900 p-5 shadow-xl shadow-slate-950/50 lg:sticky lg:top-6 lg:h-fit">
          <div className="mb-4">
            <h2 className="text-lg font-semibold">Queue Overview</h2>
            <p className="mt-1 text-sm text-slate-400">Live agent activity and priority routing.</p>
          </div>
          <div className="space-y-3">
            <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-3">
              <p className="text-sm text-slate-400">Active tickets</p>
              <p className="mt-1 text-2xl font-semibold">{activeTickets}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-3">
              <p className="text-sm text-slate-400">Escalations</p>
              <p className="mt-1 text-2xl font-semibold">{escalations}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-3">
              <p className="text-sm text-slate-400">AI triage confidence</p>
              <p className="mt-1 text-2xl font-semibold">{confidenceScore}</p>
            </div>
          </div>
        </aside>

        <section className="flex-1 rounded-2xl border border-slate-800 bg-slate-900 p-5 shadow-xl shadow-slate-950/50">
          {children}
        </section>
      </main>
    </div>
  );
}
