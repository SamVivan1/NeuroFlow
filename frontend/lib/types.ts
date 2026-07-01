export interface RawMpuSample {
  timestamp?: number;
  ax: number;
  ay: number;
  az: number;
  gx: number;
  gy: number;
  gz: number;
}

export interface NeuroflowTelemetry {
  // Legacy fields (kept for fallback/dashboard)
  stress_level?: number;
  tremor_intensity?: number;
  device_status?: string;

  // New strict physiological fields
  heart_rate?: number;
  rmssd?: number;
  sdnn?: number;
  pnn50?: number;
  avg_bpm_30s?: number;
  spo2?: number;

  // Device & Context
  battery_pct?: number;
  activity?: string;
  condition?: string;

  // New Clinical Interpretations (from backend)
  tremor_validity?: string;
  tremor_intensity_label?: string;
  tremor_pattern_label?: string;
  dominant_frequency_hz?: number;
  activity_artifact_score?: number;
  stress_context_label?: string;
  stress_interpretation?: string;
  motor_interpretation?: string;
  parkinson_model_class?: string;

  // Raw MPU6050 latest values (optional)
  ax?: number;
  ay?: number;
  az?: number;
  gx?: number;
  gy?: number;
  gz?: number;

  // Sample array for frequency analysis
  samples?: RawMpuSample[];
  sampling_rate_hz?: number;

  received_at?: number;
}

export interface DeviceCommands {
  haptic_intensity?: 1 | 2 | 3;
  alerts_enabled?: boolean;
  tremor_threshold?: number;
  stress_threshold?: number;
}

export interface TelemetrySnapshot extends NeuroflowTelemetry {
  received_at: number;
}

export interface SessionStats {
  avgHeartRate: number;
  avgStress: number;
  avgTremor: number;
  maxTremor: number;
  sampleCount: number;
  peakTremorTime: string | null;
}