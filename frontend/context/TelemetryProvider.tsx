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
import { isDeviceConnected } from "@/lib/telemetry-utils";

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
  const [lastReceivedAt, setLastReceivedAt] = useState<number | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const source = new EventSource("/api/telemetry");

    source.onmessage = (event) => {
      const data = JSON.parse(event.data) as TelemetrySnapshot;
      setTelemetry(data);
      setLastReceivedAt(data.received_at);
      setConnected(true);
      setHistory((prev) => [...prev.slice(-(MAX_HISTORY - 1)), data]);
    };

    source.onerror = () => {
      setConnected(false);
    };

    return () => source.close();
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setConnected(isDeviceConnected(lastReceivedAt));
    }, 1000);
    return () => clearInterval(interval);
  }, [lastReceivedAt]);

  const sendCommand = useCallback(async (commands: DeviceCommands) => {
    const response = await fetch("/api/commands", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(commands),
    });
    if (!response.ok) {
      throw new Error("Failed to send command to ESP32");
    }
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
