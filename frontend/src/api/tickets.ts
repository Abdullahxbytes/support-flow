export interface TicketApiRecord {
  id: number;
  title: string;
  description: string;
  customer_email: string;
  priority: string;
  status: string;
  execution_track: string;
  ai_draft_response?: string | null;
  rag_confidence_score?: number | null;
  created_at: string;
  updated_at: string;
}

export interface AnalyticsSummary {
  total_triaged_count: number;
  automated_resolution_rate: number;
  average_rag_confidence: number;
  category_breakdown: Record<string, number>;
}

const API_BASE_URL = 'http://localhost:8000/api/v1';

export async function fetchTickets(): Promise<TicketApiRecord[]> {
  const response = await fetch(`${API_BASE_URL}/tickets`);
  if (!response.ok) {
    throw new Error('Unable to load tickets from SupportFlow API.');
  }
  return response.json() as Promise<TicketApiRecord[]>;
}

export async function fetchAnalytics(): Promise<AnalyticsSummary> {
  const response = await fetch(`${API_BASE_URL}/analytics/triage-summary`);
  if (!response.ok) {
    throw new Error('Unable to load analytics from SupportFlow API.');
  }
  return response.json() as Promise<AnalyticsSummary>;
}
