export interface NeuroflowTelemetry {
  stress_level: number;
  heart_rate: number;
  tremor_intensity: number;
  device_status: string;
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
