export type WebSocketConnectionState = 'CONNECTING' | 'OPEN' | 'CLOSING' | 'CLOSED';

export type WebSocketEventType = 'TICKET_CREATED' | 'TICKET_TRIAGED' | 'TICKET_ESCALATED' | 'AGENT_ALERT' | 'PING';

export interface WebSocketEventPayload<T = Record<string, unknown>> {
  event: WebSocketEventType;
  timestamp: string;
  data: T;
}

export interface TicketUpdateData {
  id?: string;
  ticket_id?: string;
  title?: string;
  status?: string;
  priority?: string;
  tenant_id?: string;
  summary?: string;
  suggested_response?: string;
}

export interface AgentAlertData {
  message: string;
  severity?: 'info' | 'warning' | 'critical';
}
