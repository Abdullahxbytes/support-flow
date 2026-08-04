import { useEffect, useMemo, useState } from 'react';
import { fetchTickets, TicketApiRecord } from '../../api/tickets';
import { useWebSocket } from '../../hooks/useWebSocket';
import { TicketUpdateData, WebSocketEventPayload } from '../../types/websocket';

const DEFAULT_URL = 'ws://localhost:8000/ws/tickets';
const TOKEN = 'supportflow-websocket-token';

export function LiveTicketQueue() {
  const { isConnected, lastEvent, connectionError } = useWebSocket<WebSocketEventPayload<TicketUpdateData>['data']>(DEFAULT_URL, TOKEN);
  const [tickets, setTickets] = useState<TicketApiRecord[]>([]);

  const derivedStatus = useMemo(() => {
    if (connectionError) {
      return 'Reconnecting';
    }
    return isConnected ? 'Streaming live updates' : 'Waiting for socket';
  }, [connectionError, isConnected]);

  useEffect(() => {
    let active = true;

    async function loadTickets() {
      try {
        const records = await fetchTickets();
        if (!active) {
          return;
        }
        setTickets(records);
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
    if (!lastEvent) {
      return;
    }

    const payload = lastEvent.data as TicketUpdateData;
    if (!payload?.id) {
      return;
    }

    if (lastEvent.event === 'TICKET_TRIAGED' || lastEvent.event === 'TICKET_ESCALATED') {
      setTickets((current) => {
        const existingIndex = current.findIndex((ticket) => ticket.id === Number(payload.id));
        if (existingIndex >= 0) {
          const next = [...current];
          next[existingIndex] = {
            ...next[existingIndex],
            title: payload.title ?? next[existingIndex].title,
            status: payload.status ?? next[existingIndex].status,
            priority: payload.priority ?? next[existingIndex].priority,
            description: payload.summary ?? next[existingIndex].description,
          };
          return next;
        }

        return [
          {
            id: Number(payload.id),
            title: payload.title ?? 'Updated ticket',
            description: payload.summary ?? '',
            customer_email: '',
            priority: payload.priority ?? 'MEDIUM',
            status: payload.status ?? 'NEW',
            execution_track: 'UNASSIGNED',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
          ...current,
        ];
      });
    }
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

      <div className="overflow-hidden rounded-2xl border border-slate-800">
        <div className="grid grid-cols-[1.2fr_0.6fr_0.6fr] border-b border-slate-800 bg-slate-950/70 px-4 py-3 text-sm font-medium text-slate-300">
          <span>Ticket</span>
          <span>Status</span>
          <span>Priority</span>
        </div>
        <div className="divide-y divide-slate-800 bg-slate-900/70">
          {tickets.map((ticket) => (
            <div key={ticket.id} className="grid grid-cols-[1.2fr_0.6fr_0.6fr] items-center px-4 py-3 text-sm">
              <div>
                <p className="font-medium text-slate-100">#{ticket.id}</p>
                <p className="text-slate-400">{ticket.title}</p>
              </div>
              <span className="rounded-full bg-slate-800 px-2.5 py-1 text-center text-xs uppercase tracking-[0.2em] text-slate-300">
                {ticket.status}
              </span>
              <span className="text-slate-300">{ticket.priority}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
