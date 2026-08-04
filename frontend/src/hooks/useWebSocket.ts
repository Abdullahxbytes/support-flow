import { useEffect, useMemo, useRef, useState } from 'react';
import { WebSocketEventPayload, WebSocketEventType } from '../types/websocket';

interface UseWebSocketResult<T = Record<string, unknown>> {
  isConnected: boolean;
  lastEvent: WebSocketEventPayload<T> | null;
  sendEvent: (event: WebSocketEventPayload<T>) => void;
  connectionError: string | null;
}

const MAX_RETRIES = 5;
const BASE_RETRY_DELAY_MS = 1000;

export function useWebSocket<T = Record<string, unknown>>(url: string, token: string): UseWebSocketResult<T> {
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<WebSocketEventPayload<T> | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const heartbeatRef = useRef<number | null>(null);

  const resolvedUrl = useMemo(() => {
    const wsUrl = new URL(url);
    wsUrl.searchParams.set('token', token);
    return wsUrl.toString();
  }, [url, token]);

  useEffect(() => {
    let isMounted = true;

    const connect = () => {
      if (!isMounted) {
        return;
      }

      const nextSocket = new WebSocket(resolvedUrl);
      socketRef.current = nextSocket;
      setConnectionError(null);

      nextSocket.addEventListener('open', () => {
        if (!isMounted) {
          return;
        }
        setIsConnected(true);
        setConnectionError(null);
        retriesRef.current = 0;
      });

      nextSocket.addEventListener('message', (event) => {
        try {
          const parsed = JSON.parse(event.data as string) as Partial<WebSocketEventPayload<T>>;
          if (!parsed || typeof parsed !== 'object' || !parsed.event || !parsed.timestamp) {
            return;
          }

          const normalizedEvent: WebSocketEventPayload<T> = {
            event: parsed.event as WebSocketEventType,
            timestamp: parsed.timestamp,
            data: (parsed.data ?? {}) as T,
          };

          setLastEvent(normalizedEvent);
        } catch (error) {
          setConnectionError('Received invalid WebSocket payload.');
        }
      });

      nextSocket.addEventListener('close', () => {
        if (!isMounted) {
          return;
        }
        setIsConnected(false);
        if (retriesRef.current < MAX_RETRIES) {
          const delay = BASE_RETRY_DELAY_MS * 2 ** retriesRef.current;
          retriesRef.current += 1;
          setConnectionError(`Connection lost. Retrying in ${delay}ms...`);
          window.setTimeout(connect, delay);
        } else {
          setConnectionError('Unable to reconnect to SupportFlow WebSocket.');
        }
      });

      nextSocket.addEventListener('error', () => {
        if (!isMounted) {
          return;
        }
        setConnectionError('WebSocket stream error.');
      });
    };

    connect();

    return () => {
      isMounted = false;
      if (heartbeatRef.current) {
        window.clearInterval(heartbeatRef.current);
      }
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [resolvedUrl]);

  const sendEvent = (event: WebSocketEventPayload<T>) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(event));
    }
  };

  return {
    isConnected,
    lastEvent,
    sendEvent,
    connectionError,
  };
}
