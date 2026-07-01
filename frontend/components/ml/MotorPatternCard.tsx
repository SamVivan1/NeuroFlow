"use client";

import { useTelemetry } from "@/context/TelemetryProvider";
import { Icon } from "@/components/Icon";

export default function MotorPatternCard() {
  const { telemetry, connected } = useTelemetry();

  if (!telemetry || !connected) {
    return (
      <section className="border border-slate-300/30 rounded-2xl p-5 mt-4 bg-slate-50/50">
        <h2 className="m-0 text-lg font-bold">Clinical Interpretation</h2>
        <p className="mt-2 text-sm text-slate-500">Waiting for device telemetry to begin analysis...</p>
      </section>
    );
  }

  const {
    tremor_validity,
    tremor_intensity_label,
    tremor_pattern_label,
    dominant_frequency_hz,
    activity_artifact_score,
    stress_context_label,
    stress_interpretation,
    motor_interpretation,
    parkinson_model_class,
  } = telemetry;

  const isArtifact = tremor_validity === "invalid";
  const artifactScoreStr = activity_artifact_score ? (activity_artifact_score * 100).toFixed(0) + "%" : "0%";
  const freqStr = dominant_frequency_hz ? dominant_frequency_hz.toFixed(1) + " Hz" : "—";

  return (
    <section className="border border-slate-300/50 rounded-3xl p-6 mt-4 bg-white shadow-sm relative overflow-hidden">
      <div className="absolute top-0 right-0 p-8 opacity-[0.03] text-teal-900 pointer-events-none">
        <Icon name="biotech" className="text-8xl scale-125" />
      </div>

      <div className="relative z-10">
        <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
          <Icon name="psychology" className="text-teal-600" />
          Clinical Analysis
        </h2>
        
        <div className="mt-3 text-xs font-semibold uppercase tracking-wider text-amber-600 bg-amber-50 px-3 py-1.5 rounded-lg border border-amber-200 inline-block mb-4">
          ⚠️ Not a medical diagnosis. HRV used for context.
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <InfoBox 
            label="Motor Pattern" 
            value={parkinson_model_class || tremor_pattern_label || "Normal"} 
            highlight={parkinson_model_class === "Parkinson-like Pattern" ? "danger" : "normal"}
          />
          <InfoBox 
            label="Stress Context" 
            value={stress_context_label || "Normal"} 
            highlight={stress_context_label?.includes("amplified") ? "warning" : "normal"}
          />
          <InfoBox label="Tremor Intensity" value={tremor_intensity_label || "No Tremor"} />
          <InfoBox label="Dominant Frequency" value={freqStr} />
          
          <div className="col-span-1 sm:col-span-2">
            <InfoBox 
              label="Artifact Gating" 
              value={isArtifact ? "Motion Artifact Detected (Analysis Suspended)" : "Valid Stationary Window"} 
              highlight={isArtifact ? "danger" : "success"}
            />
          </div>
        </div>

        <div className="mt-5 space-y-3">
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
            <h4 className="text-xs uppercase font-bold text-slate-400 mb-1">Motor Interpretation</h4>
            <p className="text-sm font-medium text-slate-700 leading-relaxed">
              {motor_interpretation || "Awaiting sufficient data..."}
            </p>
          </div>
          
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
            <h4 className="text-xs uppercase font-bold text-slate-400 mb-1">Stress Interpretation</h4>
            <p className="text-sm font-medium text-slate-700 leading-relaxed">
              {stress_interpretation || "Awaiting sufficient data..."}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

function InfoBox({ label, value, highlight = "normal" }: { label: string; value: string; highlight?: "normal" | "danger" | "warning" | "success" }) {
  const bgColors = {
    normal: "bg-slate-50 border-slate-200 text-slate-800",
    danger: "bg-rose-50 border-rose-200 text-rose-800",
    warning: "bg-amber-50 border-amber-200 text-amber-800",
    success: "bg-teal-50 border-teal-200 text-teal-800",
  };

  return (
    <div className={`border rounded-xl p-3 ${bgColors[highlight]}`}>
      <div className="text-[11px] uppercase font-bold opacity-60 mb-1 tracking-wider">{label}</div>
      <div className="text-sm font-semibold">{value}</div>
    </div>
  );
}
