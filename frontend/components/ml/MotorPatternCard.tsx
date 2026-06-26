"use client";

import { useState } from "react";

type MotorPatternResponse = {
  subject_id: string;
  condition: string;
  true_label: number;
  model_name: string;
  score: number;
  threshold: number;
  predicted_label: number;
  predicted_class: string;
  interpretation: string;
  missing_feature_count: number;
  extra_feature_count: number;
  demo_note: string;
};

export default function MotorPatternCard() {
  const [data, setData] = useState<MotorPatternResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function runDemoInference() {
    setLoading(true);
    setErrorMessage(null);

    try {
      const response = await fetch("/api/ml/motor-pattern/demo", {
        method: "GET",
        cache: "no-store",
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof result?.detail === "string"
            ? result.detail
            : result?.error ?? "ML inference failed",
        );
      }

      setData(result);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Unknown error",
      );
    } finally {
      setLoading(false);
    }
  }

  const isParkinsonPattern = data?.predicted_label === 1;

  return (
    <section
      style={{
        border: "1px solid rgba(148, 163, 184, 0.35)",
        borderRadius: "18px",
        padding: "18px",
        marginTop: "18px",
        background: "rgba(15, 23, 42, 0.04)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: "12px" }}>
        <div>
          <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 700 }}>
            Motor Pattern Analysis
          </h2>
          <p style={{ margin: "6px 0 0", fontSize: "13px", opacity: 0.75 }}>
            Baseline ML detector dari dataset PADS. Bukan diagnosis final dan belum stress-tremor classifier.
          </p>
        </div>

        <button
          type="button"
          onClick={runDemoInference}
          disabled={loading}
          style={{
            border: "0",
            borderRadius: "12px",
            padding: "10px 14px",
            cursor: loading ? "not-allowed" : "pointer",
            fontWeight: 700,
          }}
        >
          {loading ? "Analyzing..." : "Run Demo"}
        </button>
      </div>

      {errorMessage && (
        <p style={{ marginTop: "14px", color: "#b91c1c", fontSize: "14px" }}>
          {errorMessage}
        </p>
      )}

      {data && (
        <div style={{ marginTop: "16px", display: "grid", gap: "10px" }}>
          <div
            style={{
              borderRadius: "14px",
              padding: "14px",
              background: isParkinsonPattern
                ? "rgba(239, 68, 68, 0.10)"
                : "rgba(34, 197, 94, 0.10)",
            }}
          >
            <div style={{ fontSize: "13px", opacity: 0.75 }}>
              Prediction
            </div>
            <div style={{ fontSize: "20px", fontWeight: 800 }}>
              {data.predicted_class}
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
            <InfoBox label="Score" value={data.score.toFixed(4)} />
            <InfoBox label="Threshold" value={data.threshold.toFixed(4)} />
            <InfoBox label="Model" value={data.model_name} />
            <InfoBox label="Subject" value={`${data.subject_id} (${data.condition})`} />
          </div>

          <p style={{ margin: 0, fontSize: "14px", lineHeight: 1.5 }}>
            {data.interpretation}
          </p>

          <p style={{ margin: 0, fontSize: "12px", opacity: 0.7 }}>
            {data.demo_note}
          </p>
        </div>
      )}
    </section>
  );
}

function InfoBox({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        border: "1px solid rgba(148, 163, 184, 0.25)",
        borderRadius: "12px",
        padding: "10px",
      }}
    >
      <div style={{ fontSize: "12px", opacity: 0.65 }}>{label}</div>
      <div style={{ fontSize: "14px", fontWeight: 700 }}>{value}</div>
    </div>
  );
}
