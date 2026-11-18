import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { WebSocketAuctionPayload } from '../types';

interface WebSocketContextType {
  isConnected: boolean;
  clockOffsetMs: number;
  getServerNow: () => Date;
  subscribeRfq: (rfqId: string, handler: (msg: WebSocketAuctionPayload) => void) => () => void;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [clockOffsetMs, setClockOffsetMs] = useState<number>(0);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const activeSocketsRef = useRef<Map<string, WebSocket>>(new Map());
  const handlersRef = useRef<Map<string, Set<(msg: WebSocketAuctionPayload) => void>>>(new Map());

  // Function to return current estimated server time
  const getServerNow = useCallback(() => {
    return new Date(Date.now() + clockOffsetMs);
  }, [clockOffsetMs]);

  const subscribeRfq = useCallback((rfqId: string, handler: (msg: WebSocketAuctionPayload) => void) => {
    if (!handlersRef.current.has(rfqId)) {
      handlersRef.current.set(rfqId, new Set());
    }
    handlersRef.current.get(rfqId)!.add(handler);

    // If socket doesn't exist for this RFQ, open one
    const connectSocket = () => {
      if (activeSocketsRef.current.has(rfqId)) return;

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const token = localStorage.getItem('meridian_token');
      const wsUrl = `${protocol}//${window.location.host}/ws/rfqs/${rfqId}`;
      const socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        setIsConnected(true);
        // First-message authentication
        if (token) {
          socket.send(JSON.stringify({ action: 'AUTH', token }));
        }
        // Request clock sync
        const clientSentMs = Date.now();
        socket.send(JSON.stringify({ action: 'CLOCK_SYNC', client_sent_ms: clientSentMs }));
        // Broadcast reconnect event so pages can resync state
        const subscribers = handlersRef.current.get(rfqId);
        if (subscribers) {
          subscribers.forEach((sub) => sub({ event_type: 'RECONNECTED', rfq_id: rfqId, server_time: new Date().toISOString(), data: {} }));
        }
      };

      socket.onmessage = (event) => {
        try {
          const payload: WebSocketAuctionPayload = JSON.parse(event.data);
          const clientReceiveMs = Date.now();

          // Calculate server time offset using offset = t_server + RTT/2 - t_client_receive
          if (payload.event_type === 'CLOCK_SYNC' && (payload as any).client_sent_ms) {
            const rtt = clientReceiveMs - (payload as any).client_sent_ms;
            const serverMs = new Date(payload.server_time).getTime();
            const calculatedOffset = serverMs + (rtt / 2) - clientReceiveMs;
            setClockOffsetMs(calculatedOffset);
          } else if (payload.server_time) {
            const serverMs = new Date(payload.server_time).getTime();
            const calculatedOffset = serverMs - clientReceiveMs;
            setClockOffsetMs(calculatedOffset);
          }

          // Dispatch to all subscribers for this rfqId
          const subscribers = handlersRef.current.get(rfqId);
          if (subscribers) {
            subscribers.forEach((sub) => sub(payload));
          }
        } catch {
          // ignore parse errors
        }
      };

      socket.onclose = () => {
        activeSocketsRef.current.delete(rfqId);
        setIsConnected(activeSocketsRef.current.size > 0);
        // If there are still active subscribers, automatically schedule reconnect
        const subs = handlersRef.current.get(rfqId);
        if (subs && subs.size > 0) {
          setTimeout(() => {
            if (handlersRef.current.get(rfqId)?.size) {
              connectSocket();
            }
          }, 1500);
        }
      };

      socket.onerror = () => {
        socket.close();
      };

      activeSocketsRef.current.set(rfqId, socket);
    };

    if (!activeSocketsRef.current.has(rfqId)) {
      connectSocket();
    }

    // Unsubscribe cleanup
    return () => {
      const subscribers = handlersRef.current.get(rfqId);
      if (subscribers) {
        subscribers.delete(handler);
        if (subscribers.size === 0) {
          handlersRef.current.delete(rfqId);
          const socket = activeSocketsRef.current.get(rfqId);
          if (socket) {
            socket.close();
            activeSocketsRef.current.delete(rfqId);
          }
        }
      }
    };
  }, []);

  return (
    <WebSocketContext.Provider value={{ isConnected, clockOffsetMs, getServerNow, subscribeRfq }}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};

