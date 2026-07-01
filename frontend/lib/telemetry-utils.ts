import type { NeuroflowTelemetry } from "./types";

const DEVICE_TIMEOUT_MS = 10_000;
export const STRESS_HIGH_THRESHOLD = 75;
export const TREMOR_ALARM_THRESHOLD = 70;

type UnknownPayload = Record<string, unknown>;

function asObject(value: unknown): UnknownPayload | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as UnknownPayload;
  }

  return null;
}

function pickNumber(
  payload: UnknownPayload,
  keys: string[],
  fallback = 0,
): number {
  for (const key of keys) {
    const value = payload[key];

    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }

    if (typeof value === "string") {
      const parsed = Number(value);

      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
  }

  return fallback;
}

function pickString(
  payload: UnknownPayload,
  keys: string[],
  fallback: string,
): string {
  for (const key of keys) {
    const value = payload[key];

    if (typeof value === "string" && value.trim().length > 0) {
      return value;
    }
  }

  return fallback;
}

function pickNestedObject(
  payload: UnknownPayload,
  keys: string[],
): UnknownPayload | null {
  for (const key of keys) {
    const nested = asObject(payload[key]);

    if (nested) {
      return nested;
    }
  }

  return null;
}

export function parseTelemetryPayload(rawPayload: string): NeuroflowTelemetry | null {
  try {
    const parsed = JSON.parse(rawPayload);
    const payload = asObject(parsed);

    if (!payload) {
      return null;
    }

    const mpu =
      pickNestedObject(payload, ["mpu", "mpu6050", "imu", "sensor"]) ?? payload;

    const receivedAt =
      pickNumber(payload, ["received_at", "timestamp", "time"], Date.now());

    const normalizedReceivedAt =
      receivedAt > 0 && receivedAt < 10_000_000_000
        ? receivedAt * 1000
        : receivedAt;

    return {
      stress_level: pickNumber(payload, ["stress_level", "stressLevel", "stress"], 0),
      heart_rate: pickNumber(payload, ["heart_rate", "heartRate", "bpm", "hr"], 0),
      rmssd: pickNumber(payload, ["rmssd"], 0),
      sdnn: pickNumber(payload, ["sdnn"], 0),
      pnn50: pickNumber(payload, ["pnn50"], 0),
      avg_bpm_30s: pickNumber(payload, ["avg_bpm_30s", "avgBpm30s"], 0),
      spo2: pickNumber(payload, ["spo2"], 0),
      battery_pct: pickNumber(payload, ["battery_pct", "batteryPct", "battery"], 100),
      activity: pickString(payload, ["activity"], "STATIONARY"),
      condition: pickString(payload, ["condition"], "UNKNOWN"),
      tremor_validity: pickString(payload, ["tremor_validity"], ""),
      tremor_intensity_label: pickString(payload, ["tremor_intensity_label"], ""),
      tremor_pattern_label: pickString(payload, ["tremor_pattern_label"], ""),
      stress_context_label: pickString(payload, ["stress_context_label"], ""),
      stress_interpretation: pickString(payload, ["stress_interpretation"], ""),
      motor_interpretation: pickString(payload, ["motor_interpretation"], ""),
      parkinson_model_class: pickString(payload, ["parkinson_model_class"], ""),
      dominant_frequency_hz: pickNumber(payload, ["dominant_frequency_hz"], 0),
      activity_artifact_score: pickNumber(payload, ["activity_artifact_score"], 0),
      tremor_intensity: pickNumber(
        payload,
        ["tremor_intensity", "tremorIntensity", "tremor", "tremor_score"],
        0,
      ),
      device_status: pickString(
        payload,
        ["device_status", "deviceStatus", "status"],
        "connected",
      ),
      received_at: normalizedReceivedAt,

      ax: pickNumber(mpu, ["ax", "acc_x", "accel_x", "accelX", "accelerometer_x", "AccX"], 0),
      ay: pickNumber(mpu, ["ay", "acc_y", "accel_y", "accelY", "accelerometer_y", "AccY"], 0),
      az: pickNumber(mpu, ["az", "acc_z", "accel_z", "accelZ", "accelerometer_z", "AccZ"], 0),

      gx: pickNumber(mpu, ["gx", "gyro_x", "gyroX", "gyroscope_x", "GyroX"], 0),
      gy: pickNumber(mpu, ["gy", "gyro_y", "gyroY", "gyroscope_y", "GyroY"], 0),
      gz: pickNumber(mpu, ["gz", "gyro_z", "gyroZ", "gyroscope_z", "GyroZ"], 0),
      
      sampling_rate_hz: pickNumber(payload, ["sampling_rate_hz", "samplingRateHz", "fs"], 0),
      samples: Array.isArray(payload.samples) ? payload.samples as any[] : undefined,
    };
  } catch {
    return null;
  }
}

export function formatBpm(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value) || value <= 0) {
    return "-- bpm";
  }

  return `${Math.round(value)} bpm`;
}

export function tremorToPercent(value: number | null | undefined): number {
  if (value == null || !Number.isFinite(value)) {
    return 0;
  }

  return Math.max(0, Math.min(100, Math.round(value)));
}

export function getStressLabel(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "Unknown";
  }

  if (value >= STRESS_HIGH_THRESHOLD) {
    return "High Stress";
  }

  if (value >= 50) {
    return "Moderate Stress";
  }

  return "Low Stress";
}

export function getStressBadgeClass(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "badge badge-muted";
  }

  if (value >= STRESS_HIGH_THRESHOLD) {
    return "badge badge-danger";
  }

  if (value >= 50) {
    return "badge badge-warning";
  }

  return "badge badge-success";
}

export function getTremorLabel(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "Unknown";
  }

  if (value >= TREMOR_ALARM_THRESHOLD) {
    return "High Tremor";
  }

  if (value >= 40) {
    return "Moderate Tremor";
  }

  if (value > 0) {
    return "Low Tremor";
  }

  return "No Tremor";
}

export function getTremorStatus(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "unknown";
  }

  if (value >= TREMOR_ALARM_THRESHOLD) {
    return "alarm";
  }

  if (value >= 40) {
    return "warning";
  }

  return "stable";
}

export function buildHrSparkline(
  history: Array<Pick<NeuroflowTelemetry, "heart_rate">>,
  limit = 24,
): number[] {
  const values = history
    .map((item) => item.heart_rate)
    .filter((value) => Number.isFinite(value) && value > 0)
    .slice(-limit);

  if (values.length === 0) {
    return Array.from({ length: limit }, () => 8);
  }

  if (values.length === 1) {
    return Array.from({ length: limit }, () => 40);
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);

  const normalized = values.map((value) => {
    const percent = ((value - min) / range) * 100;

    // Minimal 8 supaya bar tetap terlihat.
    return Math.max(8, Math.round(percent));
  });

  const paddingCount = Math.max(0, limit - normalized.length);
  const padding = Array.from({ length: paddingCount }, () => 8);

  return [...padding, ...normalized];
}

export function isDeviceConnected(lastReceivedAt: number | null): boolean {
  if (!lastReceivedAt) {
    return false;
  }

  return Date.now() - lastReceivedAt <= DEVICE_TIMEOUT_MS;
}

export function computeSessionStats(history: Array<Pick<NeuroflowTelemetry, "heart_rate" | "stress_level" | "tremor_intensity" | "received_at">>) {
  const sampleCount = history.length;
  if (sampleCount === 0) {
    return { sampleCount, avgStress: 0, avgHeartRate: 0, avgTremor: 0, maxTremor: 0, peakTremorTime: null };
  }
  
  const avgStress = history.reduce((acc, h) => acc + (h.stress_level || 0), 0) / sampleCount;
  const avgHeartRate = Math.round(history.reduce((acc, h) => acc + (h.heart_rate || 0), 0) / sampleCount);
  const avgTremor = history.reduce((acc, h) => acc + (h.tremor_intensity || 0), 0) / sampleCount;
  const maxTremor = Math.max(...history.map(h => h.tremor_intensity || 0));
  const peakTremorObj = history.find(h => h.tremor_intensity === maxTremor);
  const peakTremorTime = peakTremorObj && peakTremorObj.received_at ? new Date(peakTremorObj.received_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'}) : null;
  
  return { sampleCount, avgStress: Math.round(avgStress), avgHeartRate, avgTremor, maxTremor, peakTremorTime };
}