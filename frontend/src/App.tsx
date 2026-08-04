import { useEffect, useState } from 'react';
import { AnalyticsSummary, fetchAnalytics } from './api/tickets';
import { DashboardLayout } from './components/dashboard/DashboardLayout';
import { LiveTicketQueue } from './components/dashboard/LiveTicketQueue';
import { useWebSocket } from './hooks/useWebSocket';

const DEFAULT_URL = 'ws://localhost:8000/ws/tickets';
const TOKEN = 'supportflow-websocket-token';

export default function App() {
  const { isConnected, connectionError } = useWebSocket(DEFAULT_URL, TOKEN);
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);

  useEffect(() => {
    let active = true;

    async function loadAnalytics() {
      try {
        const summary = await fetchAnalytics();
        if (!active) {
          return;
        }
        setAnalytics(summary);
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
    <DashboardLayout
      connectionState={isConnected ? 'OPEN' : connectionError ? 'CLOSED' : 'CONNECTING'}
      connectionError={connectionError}
      analytics={analytics}
    >
      <LiveTicketQueue />
    </DashboardLayout>
  );
}
