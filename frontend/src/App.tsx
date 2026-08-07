import { useEffect, useState } from 'react';
import { AnalyticsSummary, fetchAnalytics } from './api/tickets';
import { DashboardLayout } from './components/dashboard/DashboardLayout';
import { LiveTicketQueue } from './components/dashboard/LiveTicketQueue';
import { ChatWidget } from './components/widget/ChatWidget';
import { useWebSocket } from './hooks/useWebSocket';

const DEFAULT_URL = 'ws://localhost:8000/ws/tickets';
const TOKEN = 'supportflow-websocket-token';

interface QueueMetrics {
  activeTickets: number;
  escalations: number;
  aiConfidence: number;
}

export default function App() {
  const { isConnected, connectionError } = useWebSocket(DEFAULT_URL, TOKEN);
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [queueMetrics, setQueueMetrics] = useState<QueueMetrics>({
    activeTickets: 0,
    escalations: 0,
    aiConfidence: 0,
  });

  useEffect(() => {
    let active = true;

    async function loadAnalytics() {
      try {
        const summary = await fetchAnalytics();
        if (!active) {
          return;
        }
        setAnalytics(summary);
        setQueueMetrics((prev) => ({
          ...prev,
          aiConfidence: Number((summary.average_rag_confidence * 100).toFixed(1)),
        }));
      } catch (error) {
        console.error(error);
      }
    }

    loadAnalytics();

    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="relative min-h-screen bg-slate-950">
      <DashboardLayout
        connectionState={isConnected ? 'OPEN' : connectionError ? 'CLOSED' : 'CONNECTING'}
        connectionError={connectionError}
        analytics={analytics}
        queueMetrics={queueMetrics}
      >
        <LiveTicketQueue onMetricsChange={setQueueMetrics} />
      </DashboardLayout>
      <ChatWidget />
    </div>
  );
}
