"use client";

import { Icon } from "@/components/Icon";
import { TopAppBar } from "@/components/layout/TopAppBar";
import { useTelemetry } from "@/context/TelemetryProvider";
import { computeSessionStats, tremorToPercent } from "@/lib/telemetry-utils";

function buildChartPaths(history: ReturnType<typeof useTelemetry>["history"]) {
  const recent = history.slice(-20);
  if (recent.length < 2) {
    return {
      hr: "M0,80 Q25,70 50,75 T100,70",
      tremor: "M0,90 Q25,85 50,60 T100,95",
    };
  }

  const toY = (value: number, max: number) => 95 - (value / max) * 70;
  const toNumber = (value: number | undefined, fallback: number) => value ?? fallback;

  const maxHr = Math.max(...recent.map((h) => toNumber(h.heart_rate, 0)), 1);
  const maxTremor = Math.max(...recent.map((h) => toNumber(h.tremor_intensity, 0)), 0.01);

  const hrPoints = recent.map((h, i) => {
    const x = (i / (recent.length - 1)) * 100;
    const y = toY(toNumber(h.heart_rate, 0), maxHr);
    return `${i === 0 ? "M" : "L"}${x},${y}`;
  });

  const tremorPoints = recent.map((h, i) => {
    const x = (i / (recent.length - 1)) * 100;
    const y = toY(toNumber(h.tremor_intensity, 0), maxTremor);
    return `${i === 0 ? "M" : "L"}${x},${y}`;
  });

  return { hr: hrPoints.join(" "), tremor: tremorPoints.join(" ") };
}

export default function ReportsPage() {
  const { history, connected } = useTelemetry();
  const stats = computeSessionStats(history);
  const paths = buildChartPaths(history);

  const stressControlled =
    stats.sampleCount > 0
      ? Math.max(0, 100 - Math.round(stats.avgStress))
      : 0;

  return (
    <>
      <TopAppBar showConnection={false} />
      <main className="pt-24 px-4 max-w-4xl mx-auto space-y-6 pb-8">
        <section className="bg-primary-container text-white rounded-xl p-6 shadow-lg relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 opacity-10">
            <Icon name="analytics" style={{ fontSize: 120 }} />
          </div>
          <div className="relative z-10">
            <p className="text-label-lg font-semibold tracking-wide text-on-primary-container mb-2">
              Laporan Neuro-Profile: Sesi Live
            </p>
            <h2 className="font-display text-headline-lg-mobile font-bold mb-4">
              {stats.sampleCount > 0
                ? `Stres terkontrol ${stressControlled}% sesi ini`
                : "Menunggu data dari ESP32"}
            </h2>
            <div className="flex gap-4 items-center flex-wrap">
              <div className="bg-secondary-container text-on-secondary-container px-4 py-2 rounded-lg flex items-center gap-2">
                <Icon name="trending_down" className="text-sm" />
                <span className="text-label-lg font-semibold tracking-wide">
                  Tremor avg {(stats.avgTremor * 100).toFixed(1)}%
                </span>
              </div>
              <div className="bg-surface-container-highest/20 px-4 py-2 rounded-lg flex items-center gap-2">
                <Icon name="favorite" className="text-sm" />
                <span className="text-label-lg font-semibold tracking-wide">
                  HR avg {stats.avgHeartRate || "—"} BPM
                </span>
              </div>
            </div>
          </div>
        </section>

        <section className="bg-white rounded-xl shadow-sm border border-surface-variant p-6 space-y-6">
          <div className="flex justify-between items-start">
            <div>
              <h3 className="font-display text-headline-md font-semibold text-primary">
                Korelasi Heart Rate & Tremor
              </h3>
              <p className="text-body-md text-on-surface-variant">
                Data live dari MQTT — {stats.sampleCount} sampel
              </p>
            </div>
            <div className="flex gap-2">
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-secondary">
                <span className="w-2 h-2 rounded-full bg-secondary" />
                HR
              </span>
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-error">
                <span className="w-2 h-2 rounded-full bg-error" />
                Tremor
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="md:col-span-3 h-64 bg-surface-container-low rounded-xl relative flex items-end justify-between p-4">
              <svg
                className="absolute inset-0 w-full h-full px-4 pb-8"
                preserveAspectRatio="none"
                viewBox="0 0 100 100"
              >
                <path d={paths.hr} fill="none" stroke="#006b5f" strokeWidth="2" />
                <path
                  d={paths.tremor}
                  fill="none"
                  stroke="#ba1a1a"
                  strokeDasharray="4"
                  strokeWidth="2"
                />
              </svg>
              {!connected && (
                <p className="absolute inset-0 flex items-center justify-center text-on-surface-variant text-body-md">
                  Hubungkan wristband ESP32 untuk melihat grafik
                </p>
              )}
            </div>
            <div className="bg-surface-container-highest rounded-xl p-4 flex flex-col justify-center items-center text-center">
              <p className="text-label-lg font-semibold tracking-wide text-on-surface-variant">
                Puncak Tremor
              </p>
              <span className="font-display text-stats-display font-bold text-error">
                {stats.peakTremorTime?.split(":")[0] ?? "—"}
              </span>
              <p className="text-body-md text-error">
                {stats.peakTremorTime?.split(":")[1] ?? ""}
              </p>
            </div>
          </div>
        </section>

        <section className="bg-secondary-fixed text-on-secondary-fixed rounded-xl p-6 border-l-8 border-secondary flex gap-4">
          <div className="shrink-0 w-12 h-12 bg-white/50 rounded-full flex items-center justify-center">
            <Icon name="psychiatry" className="text-secondary" />
          </div>
          <div>
            <h4 className="text-label-lg font-semibold tracking-wider uppercase mb-1">
              Wawasan Neurolog
            </h4>
            <p className="text-body-lg italic">
              {stats.sampleCount > 0
                ? stats.maxTremor > 0.4
                  ? `"Tremor mencapai puncak ${stats.peakTremorTime} dengan intensitas ${(stats.maxTremor * 100).toFixed(0)}%. Pertimbangkan sesi pernapasan sebelum aktivitas berat."`
                  : `"Tremor stabil selama sesi (${tremorToPercent(stats.avgTremor)}% rata-rata). Pertahankan rutinitas relaksasi pagi hari."`
                : '"Menunggu data biometrik dari wristband ESP32 untuk analisis klinis."'}
            </p>
          </div>
        </section>

        <section className="space-y-4">
          <h4 className="font-display text-headline-md font-semibold text-primary px-2">
            Data Sesi
          </h4>
          <div className="bg-white rounded-xl overflow-hidden shadow-sm border border-surface-variant">
            <table className="w-full text-left">
              <thead className="bg-surface-container-low">
                <tr>
                  <th className="p-4 text-label-lg font-semibold tracking-wide text-on-surface-variant">
                    Metrik
                  </th>
                  <th className="p-4 text-label-lg font-semibold tracking-wide text-on-surface-variant">
                    Nilai
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/20">
                <tr>
                  <td className="p-4 text-body-md">Rata-rata Heart Rate</td>
                  <td className="p-4 font-display font-semibold">
                    {stats.avgHeartRate || "—"} BPM
                  </td>
                </tr>
                <tr>
                  <td className="p-4 text-body-md">Rata-rata Stres</td>
                  <td className="p-4 font-display font-semibold">{stats.avgStress}%</td>
                </tr>
                <tr>
                  <td className="p-4 text-body-md">Rata-rata Tremor</td>
                  <td className="p-4 font-display font-semibold">
                    {(stats.avgTremor * 100).toFixed(1)}%
                  </td>
                </tr>
                <tr>
                  <td className="p-4 text-body-md">Sampel Diterima</td>
                  <td className="p-4 font-display font-semibold">{stats.sampleCount}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </>
  );
}
