"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { DeviceCommands, TelemetrySnapshot } from "@/lib/types";

const MAX_HISTORY = 3600;

interface TelemetryContextValue {
  telemetry: TelemetrySnapshot | null;
  history: TelemetrySnapshot[];
  connected: boolean;
  sendCommand: (commands: DeviceCommands) => Promise<void>;
}

const TelemetryContext = createContext<TelemetryContextValue | null>(null);

export function TelemetryProvider({ children }: { children: ReactNode }) {
  const [telemetry, setTelemetry] = useState<TelemetrySnapshot | null>(null);
  const [history, setHistory] = useState<TelemetrySnapshot[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    // Connect to the ML Service WebSocket Gateway
    // For local QA demo, we point directly to localhost:8000
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";
    
    let ws: WebSocket;
    let reconnectTimer: NodeJS.Timeout;

    const connectWS = () => {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // Add received_at timestamp since the dummy payload might not have it
          const snapshot: TelemetrySnapshot = {
            ...data,
            received_at: Date.now()
          };
          
          setTelemetry(snapshot);
          setHistory((prev) => [...prev.slice(-(MAX_HISTORY - 1)), snapshot]);
        } catch (e) {
          console.error("Error parsing telemetry", e);
        }
      };

      ws.onclose = () => {
        setConnected(false);
        // Auto reconnect
        reconnectTimer = setTimeout(connectWS, 3000);
      };
      
      ws.onerror = () => {
        ws.close();
      };
    };

    connectWS();

    return () => {
      clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, []);

  const sendCommand = useCallback(async (commands: DeviceCommands) => {
    // Implementation left for MQTT commands
    console.log("Sending command:", commands);
  }, []);

  const value = useMemo(
    () => ({ telemetry, history, connected, sendCommand }),
    [telemetry, history, connected, sendCommand],
  );

  return (
    <TelemetryContext.Provider value={value}>{children}</TelemetryContext.Provider>
  );
}

export function useTelemetry(): TelemetryContextValue {
  const ctx = useContext(TelemetryContext);
  if (!ctx) {
    throw new Error("useTelemetry must be used within TelemetryProvider");
  }
  return ctx;
}
