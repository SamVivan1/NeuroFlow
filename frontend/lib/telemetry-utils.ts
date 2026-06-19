import type { NeuroflowTelemetry, SessionStats, TelemetrySnapshot } from "./types";

export const TREMOR_ALARM_THRESHOLD = 0.4;
export const STRESS_HIGH_THRESHOLD = 80;
export const CONNECTION_TIMEOUT_MS = 4000;

export function getStressLabel(stress: number): string {
  if (stress < 50) return "Normal";
  if (stress < 80) return "Elevated";
  return "Tinggi";
}

export function getStressBadgeClass(stress: number): string {
  if (stress < 50) return "bg-secondary-container text-on-secondary-container";
  if (stress < 80) return "bg-tertiary-fixed text-on-tertiary-fixed";
  return "bg-error-container text-on-error-container";
}

export function getTremorLabel(intensity: number, threshold = TREMOR_ALARM_THRESHOLD): string {
  if (intensity < threshold * 0.5) return "Rendah";
  if (intensity < threshold) return "Sedang";
  return "Tinggi";
}

export function getTremorStatus(intensity: number, threshold = TREMOR_ALARM_THRESHOLD): string {
  if (intensity < threshold * 0.5) return "Stabil";
  if (intensity < threshold) return "Waspada";
  return "Aktif";
}

export function tremorToPercent(intensity: number, threshold = TREMOR_ALARM_THRESHOLD): number {
  return Math.min(100, Math.round((intensity / threshold) * 100));
}

export function isDeviceConnected(lastReceivedAt: number | null): boolean {
  if (!lastReceivedAt) return false;
  return Date.now() - lastReceivedAt < CONNECTION_TIMEOUT_MS;
}

export function formatBpm(heartRate: number): string {
  return heartRate > 0 ? String(heartRate) : "—";
}

export function computeSessionStats(history: TelemetrySnapshot[]): SessionStats {
  if (history.length === 0) {
    return {
      avgHeartRate: 0,
      avgStress: 0,
      avgTremor: 0,
      maxTremor: 0,
      sampleCount: 0,
      peakTremorTime: null,
    };
  }

  const validHr = history.filter((h) => h.heart_rate > 0);
  const avgHeartRate =
    validHr.length > 0
      ? Math.round(validHr.reduce((s, h) => s + h.heart_rate, 0) / validHr.length)
      : 0;
  const avgStress = Math.round(
    history.reduce((s, h) => s + h.stress_level, 0) / history.length,
  );
  const avgTremor =
    history.reduce((s, h) => s + h.tremor_intensity, 0) / history.length;
  const maxEntry = history.reduce((max, h) =>
    h.tremor_intensity > max.tremor_intensity ? h : max,
  );
  const peakTremorTime = new Date(maxEntry.received_at).toLocaleTimeString("id-ID", {
    hour: "2-digit",
    minute: "2-digit",
  });

  return {
    avgHeartRate,
    avgStress,
    avgTremor,
    maxTremor: maxEntry.tremor_intensity,
    sampleCount: history.length,
    peakTremorTime,
  };
}

export function parseTelemetryPayload(raw: string): NeuroflowTelemetry | null {
  try {
    const data = JSON.parse(raw) as NeuroflowTelemetry;
    if (
      typeof data.stress_level !== "number" ||
      typeof data.heart_rate !== "number" ||
      typeof data.tremor_intensity !== "number"
    ) {
      return null;
    }
    return data;
  } catch {
    return null;
  }
}

export function buildHrSparkline(history: TelemetrySnapshot[], bars = 7): number[] {
  const recent = history.filter((h) => h.heart_rate > 0).slice(-bars);
  if (recent.length === 0) return Array(bars).fill(0.3);
  const max = Math.max(...recent.map((h) => h.heart_rate));
  const min = Math.min(...recent.map((h) => h.heart_rate));
  const range = max - min || 1;
  const heights = recent.map((h) => 0.2 + ((h.heart_rate - min) / range) * 0.8);
  while (heights.length < bars) heights.unshift(0.3);
  return heights.slice(-bars);
}
