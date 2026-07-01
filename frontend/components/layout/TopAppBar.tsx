"use client";

import Link from "next/link";
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
      <div className="flex items-center gap-6">
        <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
          <Icon name="signal_cellular_alt" className="text-primary text-3xl" />
          <h1 className="font-display text-headline-md text-primary font-semibold">
            NeuroFlow
          </h1>
        </Link>
        <nav className="hidden md:flex items-center gap-4 text-sm font-medium text-on-surface-variant ml-4">
          <Link href="/" className="hover:text-primary transition-colors">Dashboard</Link>
          <Link href="/breathe" className="hover:text-primary transition-colors">Therapy</Link>
          <Link href="/reports" className="hover:text-primary transition-colors">Reports</Link>
          <Link href="/settings" className="hover:text-primary transition-colors">Settings</Link>
        </nav>
      </div>

      <div className="flex items-center gap-3">
        {showConnection && (
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${
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
              className={`text-label-lg font-semibold tracking-wide hidden sm:inline-block ${
                connected
                  ? "text-on-secondary-container"
                  : "text-on-surface-variant"
              }`}
            >
              {connected ? "ESP32 Connected" : "Device Offline"}
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
