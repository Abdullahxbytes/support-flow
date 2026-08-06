import { useEffect, useMemo, useRef, useState } from 'react';
import { fetchTickets, TicketApiRecord } from '../../api/tickets';
import { useWebSocket } from '../../hooks/useWebSocket';
import { TicketUpdateData, WebSocketEventPayload } from '../../types/websocket';

const DEFAULT_URL = 'ws://localhost:8000/ws/tickets';
const TOKEN = 'supportflow-websocket-token';

interface QueueMetrics {
  activeTickets: number;
  escalations: number;
  aiConfidence: number;
}

interface LiveTicketQueueProps {
  onMetricsChange?: (metrics: QueueMetrics) => void;
}

const statusStyles: Record<string, string> = {
  NEW: 'bg-slate-700/80 text-slate-200',
  IN_PROGRESS: 'bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30',
  RESOLVED: 'bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30',
  ESCALATED: 'bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/30',
};

const priorityStyles: Record<string, string> = {
  LOW: 'bg-slate-800 text-slate-300',
  MEDIUM: 'bg-cyan-500/15 text-cyan-300 ring-1 ring-cyan-500/30',
  HIGH: 'bg-orange-500/15 text-orange-300 ring-1 ring-orange-500/30',
  URGENT: 'bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/30',
};

const executionTrackStyles: Record<string, string> = {
  AUTOMATED: 'bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30',
  HUMAN_REVIEW: 'bg-fuchsia-500/15 text-fuchsia-300 ring-1 ring-fuchsia-500/30',
  UNASSIGNED: 'bg-slate-800 text-slate-300',
};

function calculateAverageConfidence(tickets: TicketApiRecord[]) {
  const values = tickets
    .map((ticket) => ticket.rag_confidence_score)
    .filter((value): value is number => typeof value === 'number' && Number.isFinite(value));

  if (values.length === 0) {
    return 0;
  }

  return Number(((values.reduce((sum, value) => sum + value, 0) / values.length) * 100).toFixed(1));
}

export function LiveTicketQueue({ onMetricsChange }: LiveTicketQueueProps) {
  const { isConnected, lastEvent, connectionError } = useWebSocket<WebSocketEventPayload<TicketUpdateData>['data']>(DEFAULT_URL, TOKEN);
  const [tickets, setTickets] = useState<TicketApiRecord[]>([]);
  const [highlightedTicketIds, setHighlightedTicketIds] = useState<number[]>([]);
  const [liveNotice, setLiveNotice] = useState<string | null>(null);
  const [queueMetrics, setQueueMetrics] = useState<QueueMetrics>({
    activeTickets: 0,
    escalations: 0,
    aiConfidence: 0,
  });
  const highlightTimersRef = useRef<number[]>([]);

  const derivedStatus = useMemo(() => {
    if (connectionError) {
      return 'Reconnecting';
    }
    return isConnected ? 'Streaming live updates' : 'Waiting for socket';
  }, [connectionError, isConnected]);

  useEffect(() => {
    return () => {
      highlightTimersRef.current.forEach((timer) => window.clearTimeout(timer));
      highlightTimersRef.current = [];
    };
  }, []);

  useEffect(() => {
    let active = true;

    async function loadTickets() {
      try {
        const records = await fetchTickets();
        if (!active) {
          return;
        }
        setTickets(records);
        setQueueMetrics((prev) => ({
          ...prev,
          activeTickets: records.length,
          aiConfidence: calculateAverageConfidence(records),
        }));
      } catch (error) {
        console.error(error);
      }
    }

    loadTickets();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    setQueueMetrics((prev) => ({
      ...prev,
      activeTickets: tickets.length,
      aiConfidence: calculateAverageConfidence(tickets),
    }));
  }, [tickets]);

  useEffect(() => {
    onMetricsChange?.(queueMetrics);
  }, [onMetricsChange, queueMetrics]);

  useEffect(() => {
    if (!liveNotice) {
      return;
    }

    const timeout = window.setTimeout(() => {
      setLiveNotice(null);
    }, 1600);

    return () => {
      window.clearTimeout(timeout);
    };
  }, [liveNotice]);

  useEffect(() => {
    if (!lastEvent) {
      return;
    }

    const payload = lastEvent.data as TicketUpdateData;
    const ticketId = payload.ticket_id ?? payload.id;
    if (!ticketId) {
      return;
    }

    const normalizedId = Number(ticketId);

    switch (lastEvent.event) {
      case 'TICKET_CREATED':
        setTickets((current) => {
          const existingIndex = current.findIndex((ticket) => ticket.id === normalizedId);
          if (existingIndex >= 0) {
            const next = [...current];
            next[existingIndex] = {
              ...next[existingIndex],
              title: payload.title ?? next[existingIndex].title,
              status: payload.status ?? next[existingIndex].status,
              priority: payload.priority ?? next[existingIndex].priority,
              description: payload.summary ?? payload.suggested_response ?? next[existingIndex].description,
              ai_draft_response: payload.suggested_response ?? next[existingIndex].ai_draft_response,
              updated_at: new Date().toISOString(),
            };
            return next;
          }

          return [
            {
              id: normalizedId,
              title: payload.title ?? 'Incoming support request',
              description: payload.summary ?? payload.suggested_response ?? 'New ticket arrived from the live stream.',
              customer_email: '',
              priority: payload.priority ?? 'MEDIUM',
              status: payload.status ?? 'NEW',
              execution_track: 'UNASSIGNED',
              ai_draft_response: payload.suggested_response ?? null,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            },
            ...current,
          ];
        });
        setQueueMetrics((prev) => ({ ...prev, activeTickets: prev.activeTickets + 1 }));
        setLiveNotice('New ticket received and queued live.');
        break;
      case 'TICKET_TRIAGED':
      case 'TICKET_ESCALATED':
        setTickets((current) => {
          const existingIndex = current.findIndex((ticket) => ticket.id === normalizedId);
          if (existingIndex < 0) {
            return current;
          }

          const next = [...current];
          next[existingIndex] = {
            ...next[existingIndex],
            title: payload.title ?? next[existingIndex].title,
            status: payload.status ?? next[existingIndex].status,
            priority: payload.priority ?? next[existingIndex].priority,
            description: payload.summary ?? payload.suggested_response ?? next[existingIndex].description,
            execution_track: lastEvent.event === 'TICKET_ESCALATED' ? 'HUMAN_REVIEW' : next[existingIndex].execution_track,
            ai_draft_response: payload.suggested_response ?? next[existingIndex].ai_draft_response,
            updated_at: new Date().toISOString(),
          };
          return next;
        });
        if (lastEvent.event === 'TICKET_ESCALATED') {
          setQueueMetrics((prev) => ({ ...prev, escalations: prev.escalations + 1 }));
          setLiveNotice('Ticket escalated for human review.');
        } else {
          setLiveNotice('Ticket triaged and updated in real time.');
        }
        break;
      default:
        break;
    }

    setHighlightedTicketIds((current) => (current.includes(normalizedId) ? current : [...current, normalizedId]));
    const timer = window.setTimeout(() => {
      setHighlightedTicketIds((current) => current.filter((id) => id !== normalizedId));
    }, 1400);
    highlightTimersRef.current.push(timer);
  }, [lastEvent]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Live ticket queue</h2>
          <p className="text-sm text-slate-400">{derivedStatus}</p>
        </div>
        <div className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1 text-sm text-slate-300">
          {isConnected ? '● Connected' : '○ Disconnected'}
        </div>
      </div>

      {connectionError ? (
        <div className="rounded-xl border border-amber-700/40 bg-amber-500/10 p-3 text-sm text-amber-300">
          {connectionError}
        </div>
      ) : null}

      {liveNotice ? (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-300">
          {liveNotice}
        </div>
      ) : null}

      <div className="overflow-hidden rounded-2xl border border-slate-800">
        <div className="grid grid-cols-[1.2fr_0.8fr_0.7fr] border-b border-slate-800 bg-slate-950/70 px-4 py-3 text-sm font-medium text-slate-300">
          <span>Ticket</span>
          <span>Status</span>
          <span>Priority</span>
        </div>
        <div className="divide-y divide-slate-800 bg-slate-900/70">
          {tickets.map((ticket) => {
            const isHighlighted = highlightedTicketIds.includes(ticket.id);
            return (
              <div
                key={ticket.id}
                className={`grid grid-cols-[1.2fr_0.8fr_0.7fr] items-center px-4 py-3 text-sm transition-all duration-300 ${isHighlighted ? 'bg-amber-500/10 ring-1 ring-amber-400/40' : 'bg-transparent'}`}
              >
                <div>
                  <p className="font-medium text-slate-100">#{ticket.id}</p>
                  <p className="text-slate-400">{ticket.title}</p>
                </div>
                <div className="flex flex-col gap-2">
                  <span className={`rounded-full px-2.5 py-1 text-center text-xs uppercase tracking-[0.2em] ${statusStyles[ticket.status] ?? statusStyles.NEW}`}>
                    {ticket.status}
                  </span>
                  <span className={`rounded-full px-2.5 py-1 text-center text-xs uppercase tracking-[0.2em] ${executionTrackStyles[ticket.execution_track] ?? executionTrackStyles.UNASSIGNED}`}>
                    {ticket.execution_track}
                  </span>
                </div>
                <span className={`rounded-full px-2.5 py-1 text-center text-xs uppercase tracking-[0.2em] ${priorityStyles[ticket.priority] ?? priorityStyles.MEDIUM}`}>
                  {ticket.priority}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
