"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { TopAppBar } from "@/components/layout/TopAppBar";
import { useTelemetry } from "@/context/TelemetryProvider";
import {
  STRESS_HIGH_THRESHOLD,
  TREMOR_ALARM_THRESHOLD,
} from "@/lib/telemetry-utils";

const INTENSITY_LABELS = ["Soft", "Medium", "Strong"] as const;

export default function SettingsPage() {
  const { connected, sendCommand } = useTelemetry();
  const [intensity, setIntensity] = useState(2);
  const [alertsEnabled, setAlertsEnabled] = useState(true);
  const [medReminder, setMedReminder] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("neuroflow-settings");
    if (stored) {
      const parsed = JSON.parse(stored) as {
        intensity: number;
        alertsEnabled: boolean;
        medReminder: boolean;
      };
      setIntensity(parsed.intensity);
      setAlertsEnabled(parsed.alertsEnabled);
      setMedReminder(parsed.medReminder);
    }
  }, []);

  const applySettings = async () => {
    setSaving(true);
    setSaved(false);
    try {
      const settings = { intensity, alertsEnabled, medReminder };
      localStorage.setItem("neuroflow-settings", JSON.stringify(settings));

      await sendCommand({
        haptic_intensity: intensity as 1 | 2 | 3,
        alerts_enabled: alertsEnabled,
        tremor_threshold: TREMOR_ALARM_THRESHOLD,
        stress_threshold: STRESS_HIGH_THRESHOLD,
      });
      setSaved(true);
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    const timeout = setTimeout(applySettings, 500);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intensity, alertsEnabled]);

  return (
    <>
      <TopAppBar showConnection={false} />
      <main className="px-gutter pt-24 max-w-2xl mx-auto space-y-8 pb-8">
        <section>
          <h2 className="font-display text-headline-lg-mobile font-bold mb-2">
            Pengaturan
          </h2>
          <p className="text-on-surface-variant text-body-md">
            Kelola perangkat Anda dan personalisasi pengalaman terapi.
          </p>
        </section>

        <section className="space-y-4">
          <h3 className="text-label-lg font-semibold tracking-wider text-on-surface-variant uppercase">
            Perangkat Terhubung
          </h3>
          <div className="bg-surface-container-lowest border-2 border-outline-variant/30 rounded-xl p-6 shadow-sm flex items-center justify-between">
            <div className="flex items-center gap-5">
              <div className="w-14 h-14 bg-secondary-container rounded-full flex items-center justify-center text-on-secondary-container">
                <Icon name="magic_button" style={{ fontSize: 32 }} />
              </div>
              <div>
                <h4 className="font-display text-headline-md font-semibold">
                  Wristband ESP32
                </h4>
                <div className="flex items-center gap-4 mt-1">
                  <span className="flex items-center gap-1 text-on-surface-variant text-body-md">
                    <Icon
                      name={connected ? "wifi" : "wifi_off"}
                      className="text-secondary"
                      style={{ fontSize: 18 }}
                    />
                    {connected ? "MQTT Live" : "Offline"}
                  </span>
                  <span className="flex items-center gap-1 text-on-surface-variant text-body-md">
                    <Icon
                      name="signal_cellular_4_bar"
                      className="text-secondary"
                      style={{ fontSize: 18 }}
                    />
                    {connected ? "Kuat" : "—"}
                  </span>
                </div>
              </div>
            </div>
            <Icon name="chevron_right" className="text-on-surface-variant" />
          </div>
          <p className="text-body-md text-on-surface-variant">
            Topik MQTT: <code className="text-secondary">neuroflow/device/data</code>
          </p>
        </section>

        <section className="space-y-4">
          <h3 className="text-label-lg font-semibold tracking-wider text-on-surface-variant uppercase">
            Pengaturan Haptic
          </h3>
          <div className="bg-surface-container-lowest border-2 border-outline-variant/30 rounded-xl p-6 shadow-sm space-y-6">
            <div className="flex justify-between items-end">
              <div>
                <h4 className="font-display text-headline-md font-semibold mb-1">
                  Intensitas Getaran Cue
                </h4>
                <p className="text-on-surface-variant text-body-md">
                  Dikirim ke ESP32 via MQTT commands
                </p>
              </div>
              <span className="text-secondary font-display text-headline-md font-semibold">
                {INTENSITY_LABELS[intensity - 1]}
              </span>
            </div>
            <div className="space-y-4 px-2">
              <input
                type="range"
                min={1}
                max={3}
                step={1}
                value={intensity}
                onChange={(e) => setIntensity(Number(e.target.value))}
                className="w-full h-2 bg-surface-container-high rounded-lg appearance-none cursor-pointer accent-secondary"
              />
              <div className="flex justify-between text-on-surface-variant text-label-lg font-semibold tracking-wide">
                <span>Soft</span>
                <span>Medium</span>
                <span>Strong</span>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <h3 className="text-label-lg font-semibold tracking-wider text-on-surface-variant uppercase">
            Notifikasi & Peringatan
          </h3>
          <div className="bg-surface-container-lowest border-2 border-outline-variant/30 rounded-xl overflow-hidden shadow-sm divide-y divide-outline-variant/20">
            <label className="flex items-center justify-between p-6 cursor-pointer hover:bg-surface-container-low/50 transition-colors">
              <div className="flex gap-4">
                <Icon name="medication" className="text-secondary" style={{ fontSize: 24 }} />
                <div>
                  <span className="text-body-lg block">Pengingat Obat</span>
                  <span className="text-on-surface-variant text-body-md">
                    Ingatkan jadwal minum Levodopa
                  </span>
                </div>
              </div>
              <input
                type="checkbox"
                checked={medReminder}
                onChange={(e) => setMedReminder(e.target.checked)}
                className="w-5 h-5 accent-secondary"
              />
            </label>

            <label className="flex items-center justify-between p-6 cursor-pointer hover:bg-surface-container-low/50 transition-colors">
              <div className="flex gap-4">
                <Icon name="warning" className="text-secondary" style={{ fontSize: 24 }} />
                <div>
                  <span className="text-body-lg block">Peringatan Stres</span>
                  <span className="text-on-surface-variant text-body-md">
                    Aktifkan haptic alert di ESP32
                  </span>
                </div>
              </div>
              <input
                type="checkbox"
                checked={alertsEnabled}
                onChange={(e) => setAlertsEnabled(e.target.checked)}
                className="w-5 h-5 accent-secondary"
              />
            </label>
          </div>
        </section>

        {saved && (
          <p className="text-secondary text-body-md text-center">
            Pengaturan dikirim ke ESP32
          </p>
        )}
        {saving && (
          <p className="text-on-surface-variant text-body-md text-center">
            Menyimpan...
          </p>
        )}
      </main>
    </>
  );
}
