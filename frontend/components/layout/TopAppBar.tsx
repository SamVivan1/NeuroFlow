"use client";

import { Icon } from "@/components/Icon";
import { useTelemetry } from "@/context/TelemetryProvider";

interface TopAppBarProps {
  showConnection?: boolean;
  rightSlot?: React.ReactNode;
}

export function TopAppBar({ showConnection = true, rightSlot }: TopAppBarProps) {
  const { connected } = useTelemetry();

  return (
    <header className="bg-surface shadow-sm fixed top-0 left-0 right-0 z-50 flex justify-between items-center px-gutter py-4">
      <div className="flex items-center gap-3">
        <Icon name="signal_cellular_alt" className="text-primary text-3xl" />
        <h1 className="font-display text-headline-md text-primary font-semibold">
          NeuroFlow
        </h1>
      </div>

      <div className="flex items-center gap-3">
        {showConnection && (
          <div
            className={`flex items-center gap-2 px-4 py-1.5 rounded-full ${
              connected
                ? "bg-secondary-container"
                : "bg-surface-container-high"
            }`}
          >
            <Icon
              name="circle"
              filled
              className={`text-sm ${
                connected
                  ? "text-on-secondary-container status-pulse"
                  : "text-outline"
              }`}
            />
            <span
              className={`text-label-lg font-semibold tracking-wide ${
                connected
                  ? "text-on-secondary-container"
                  : "text-on-surface-variant"
              }`}
            >
              {connected ? "ESP32 Connected" : "Menunggu ESP32"}
            </span>
          </div>
        )}
        {rightSlot ?? (
          <button type="button" className="active:scale-95 transition-transform hover:opacity-80">
            <Icon name="watch" className="text-primary text-2xl" />
          </button>
        )}
      </div>
    </header>
  );
}
