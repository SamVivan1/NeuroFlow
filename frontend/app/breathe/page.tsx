"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/Icon";
import { TopAppBar } from "@/components/layout/TopAppBar";
import { useTelemetry } from "@/context/TelemetryProvider";
import { formatBpm } from "@/lib/telemetry-utils";

const SESSION_SECONDS = 165;

export default function BreathePage() {
  const { telemetry } = useTelemetry();
  const [secondsLeft, setSecondsLeft] = useState(SESSION_SECONDS);
  const [paused, setPaused] = useState(false);
  const [isInhaling, setIsInhaling] = useState(true);
  const startBpm = useRef<number | null>(null);

  const heartRate = telemetry?.heart_rate ?? 0;

  useEffect(() => {
    if (startBpm.current === null && heartRate > 0) {
      startBpm.current = heartRate;
    }
  }, [heartRate]);

  useEffect(() => {
    if (paused || secondsLeft <= 0) return;
    const timer = setInterval(() => setSecondsLeft((s) => s - 1), 1000);
    return () => clearInterval(timer);
  }, [paused, secondsLeft]);

  useEffect(() => {
    if (paused) return;
    const cycle = setInterval(() => setIsInhaling((v) => !v), 4000);
    return () => clearInterval(cycle);
  }, [paused]);

  const bpmTrend =
    startBpm.current && heartRate > 0
      ? Math.round(((heartRate - startBpm.current) / startBpm.current) * 100)
      : null;

  const mins = Math.floor(secondsLeft / 60);
  const secs = secondsLeft % 60;

  return (
    <>
      <TopAppBar showConnection={false} />
      <main className="flex-grow flex flex-col items-center justify-center px-gutter relative pt-24 pb-8 min-h-screen">
        <div className="absolute top-28 right-8 bg-surface-container-lowest rounded-xl p-6 shadow-lg border border-outline-variant flex flex-col items-center">
          <div className="flex items-center gap-2 mb-1">
            <Icon name="favorite" filled className="text-error animate-pulse-heart" />
            <span className="text-label-lg font-semibold tracking-wide text-on-surface-variant">
              Detak Jantung
            </span>
          </div>
          <div className="flex items-baseline gap-1">
            <span className="font-display text-stats-display font-bold text-primary">
              {formatBpm(heartRate)}
            </span>
            <span className="text-label-lg font-semibold tracking-wide text-on-surface-variant">
              BPM
            </span>
          </div>
          {bpmTrend !== null && (
            <div className="mt-2 text-secondary text-label-lg font-semibold tracking-wide flex items-center gap-1">
              <Icon
                name={bpmTrend <= 0 ? "trending_down" : "trending_up"}
                className="text-sm"
              />
              <span>
                {bpmTrend <= 0 ? "Turun" : "Naik"} {Math.abs(bpmTrend)}%
              </span>
            </div>
          )}
        </div>

        <div className="mb-12 text-center">
          <span className="font-display text-stats-display font-bold text-primary">
            {String(mins).padStart(2, "0")}:{String(secs).padStart(2, "0")}
          </span>
          <p className="text-label-lg font-semibold tracking-widest text-on-surface-variant mt-2 uppercase">
            Waktu Tersisa
          </p>
        </div>

        <div className="relative flex items-center justify-center mb-16">
          <div className="absolute w-80 h-80 bg-secondary-container opacity-20 rounded-full blur-3xl" />
          <div
            className="absolute w-72 h-72 border-2 border-secondary-fixed opacity-30 rounded-full transition-all duration-[4000ms]"
            style={{
              transform: isInhaling ? "scale(1.5)" : "scale(1)",
              opacity: isInhaling ? 0.5 : 0.2,
            }}
          />
          <div
            className={`breathing-circle w-56 h-56 bg-secondary-container rounded-full flex flex-col items-center justify-center glow-teal z-10 ${
              isInhaling ? "inhale" : "exhale"
            }`}
          >
            <span className="font-display text-headline-md font-semibold text-on-secondary-container">
              {isInhaling ? "Tarik Napas" : "Hembuskan"}
            </span>
            <div className="mt-2 flex gap-1">
              <div className="w-1.5 h-1.5 rounded-full bg-on-secondary-container opacity-40" />
              <div className="w-1.5 h-1.5 rounded-full bg-on-secondary-container opacity-100" />
              <div className="w-1.5 h-1.5 rounded-full bg-on-secondary-container opacity-40" />
            </div>
          </div>
        </div>

        <div className="max-w-xs text-center">
          <h2 className="font-display text-headline-md font-semibold text-primary mb-2">
            Ikuti irama lingkaran
          </h2>
          <p className="text-body-md text-on-surface-variant">
            Fokus pada pernapasan perut Anda untuk menenangkan sistem saraf.
          </p>
        </div>

        <div className="mt-16 w-full max-w-sm flex flex-col gap-4">
          <Link
            href="/"
            className="w-full bg-primary text-on-primary py-4 px-8 rounded-xl font-display text-headline-md font-semibold hover:opacity-90 active:scale-95 transition-all shadow-lg flex items-center justify-center"
          >
            Selesai
          </Link>
          <button
            type="button"
            onClick={() => setPaused((p) => !p)}
            className="w-full border-2 border-secondary text-secondary py-4 px-8 rounded-xl text-label-lg font-semibold tracking-wide hover:bg-secondary-container/10 active:scale-95 transition-all flex items-center justify-center gap-2"
          >
            <Icon name={paused ? "play_arrow" : "pause"} />
            {paused ? "Lanjutkan Sesi" : "Jeda Sesi"}
          </button>
        </div>
      </main>
    </>
  );
}
