"use client";

import Link from "next/link";
import { Icon } from "@/components/Icon";
import { TopAppBar } from "@/components/layout/TopAppBar";
import { useTelemetry } from "@/context/TelemetryProvider";
import {
  buildHrSparkline,
  formatBpm,
  getStressBadgeClass,
  getStressLabel,
  getTremorLabel,
  getTremorStatus,
  tremorToPercent,
} from "@/lib/telemetry-utils";

export default function DashboardPage() {
  const { telemetry, history } = useTelemetry();

  const heartRate = telemetry?.heart_rate ?? 0;
  const stress = telemetry?.stress_level ?? 0;
  const tremor = telemetry?.tremor_intensity ?? 0;
  const sparkline = buildHrSparkline(history);

  return (
    <>
      <TopAppBar />
      <main className="pt-24 px-gutter max-w-2xl mx-auto space-y-6">
        <section>
          <h2 className="font-display text-headline-lg-mobile font-bold text-on-surface">
            Halo, Selamat Pagi
          </h2>
          <p className="text-body-lg text-on-surface-variant">
            Mari pantau kondisi fisik Anda hari ini.
          </p>
        </section>

        <div className="grid grid-cols-1 gap-6">
          <div className="bg-surface-container-lowest p-6 rounded-xl shadow-[0_4px_12px_rgba(42,23,0,0.05)] border-2 border-transparent hover:border-secondary-fixed transition-all">
            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center gap-3">
                <div className="bg-primary-container p-3 rounded-lg text-on-primary">
                  <Icon name="monitor_heart" />
                </div>
                <h3 className="font-display text-headline-md font-semibold text-primary">
                  Detak Jantung & Stres
                </h3>
              </div>
              <span
                className={`px-3 py-1 rounded-full text-label-lg font-semibold tracking-wide ${getStressBadgeClass(stress)}`}
              >
                {telemetry ? getStressLabel(stress) : "—"}
              </span>
            </div>

            <div className="flex items-baseline gap-2 mb-6">
              <span className="font-display text-stats-display font-bold text-primary">
                {formatBpm(heartRate)}
              </span>
              <span className="text-body-lg text-on-surface-variant">BPM</span>
            </div>

            <div className="w-full h-16 flex items-end gap-1 mb-2">
              {sparkline.map((height, i) => (
                <div
                  key={i}
                  className={`w-full rounded-t-sm ${
                    i === sparkline.length - 1
                      ? "bg-secondary-fixed"
                      : "bg-secondary-fixed-dim"
                  }`}
                  style={{ height: `${height * 100}%` }}
                />
              ))}
            </div>
            <p className="text-label-lg text-on-surface-variant">
              Stres: {telemetry ? `${stress}%` : "—"}
            </p>
          </div>

          <div className="bg-surface-container-lowest p-6 rounded-xl shadow-[0_4px_12px_rgba(42,23,0,0.05)] border-2 border-transparent hover:border-secondary-fixed transition-all">
            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center gap-3">
                <div className="bg-primary-container p-3 rounded-lg text-on-primary">
                  <Icon name="precision_manufacturing" />
                </div>
                <h3 className="font-display text-headline-md font-semibold text-primary">
                  Intensitas Tremor
                </h3>
              </div>
              <div className="flex items-center gap-1 text-on-surface-variant">
                <Icon name="info" className="text-sm" />
                <span className="text-label-lg font-semibold tracking-wide">MPU6050</span>
              </div>
            </div>

            <div className="mt-4">
              <div className="flex justify-between items-end mb-2">
                <span className="font-display text-headline-md font-semibold text-secondary">
                  {telemetry ? getTremorLabel(tremor) : "—"}
                </span>
                <span className="text-label-lg font-semibold tracking-wide text-on-surface-variant">
                  {telemetry ? getTremorStatus(tremor) : "Menunggu data"}
                </span>
              </div>
              <div className="w-full bg-surface-container h-6 rounded-full overflow-hidden border-2 border-surface-container-high">
                <div
                  className="bg-secondary h-full rounded-full transition-all duration-1000"
                  style={{ width: `${telemetry ? tremorToPercent(tremor) : 0}%` }}
                />
              </div>
              <div className="flex justify-between mt-2 text-label-lg font-semibold tracking-wide text-outline">
                <span>Low</span>
                <span>Moderate</span>
                <span>High</span>
              </div>
            </div>
          </div>
        </div>

        <section className="mt-8">
          <Link
            href="/breathe"
            className="w-full bg-primary text-on-primary min-h-[72px] rounded-xl flex items-center justify-between px-8 py-4 shadow-lg active:scale-95 transition-all group overflow-hidden relative"
          >
            <div className="flex items-center gap-4 z-10">
              <div className="breath-ring bg-secondary-fixed-dim/20 p-2 rounded-full">
                <Icon name="air" className="text-3xl" />
              </div>
              <div className="text-left">
                <span className="block font-display text-headline-md font-semibold">
                  Quick Calm
                </span>
                <span className="block text-label-lg font-semibold tracking-wide opacity-80">
                  Mulai pernapasan terpandu
                </span>
              </div>
            </div>
            <Icon
              name="chevron_right"
              className="text-3xl z-10 group-hover:translate-x-2 transition-transform"
            />
            <div className="absolute right-0 top-0 bottom-0 w-32 bg-secondary-fixed opacity-10 skew-x-[-20deg] translate-x-12" />
          </Link>
        </section>

        <section className="mt-12 rounded-2xl overflow-hidden relative h-48 flex items-center p-8 bg-primary">
          <div className="relative z-10 max-w-[60%]">
            <h4 className="font-display text-headline-md font-semibold text-on-primary mb-2">
              Catatan Harian
            </h4>
            <p className="text-body-md text-on-primary-container">
              {telemetry
                ? stress < 50
                  ? "Kondisi Anda stabil. Pertahankan rutinitas relaksasi."
                  : stress < 80
                    ? "Tingkat stres sedikit meningkat. Coba sesi pernapasan."
                    : "Stres tinggi terdeteksi. Aktifkan Quick Calm sekarang."
                : "Menunggu data dari wristband ESP32..."}
            </p>
          </div>
        </section>
      </main>
    </>
  );
}
