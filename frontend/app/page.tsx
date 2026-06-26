"use client";
import MotorPatternCard from "@/components/ml/MotorPatternCard";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { TopAppBar } from "@/components/layout/TopAppBar";
import { useTelemetry } from "@/context/TelemetryProvider";
import { StatusCard } from "@/components/widgets/StatusCard";
import { StressAlertPopup } from "@/components/widgets/StressAlertPopup";
import {
  buildHrSparkline,
  formatBpm,
  getStressLabel,
  getTremorLabel,
  getTremorStatus,
  tremorToPercent,
} from "@/lib/telemetry-utils";

export default function DashboardPage() {
  const { telemetry, history, connected } = useTelemetry();

  const heartRate = telemetry?.heart_rate ?? 0;
  const stress = telemetry?.stress_level ?? 0;
  const tremor = telemetry?.tremor_intensity ?? 0;
  const battery = telemetry?.battery_pct ?? 100;
  const sparkline = buildHrSparkline(history);

  const isHighStress = stress > 75;
  const stressColor = isHighStress ? "text-rose-500" : "text-teal-600";
  
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 selection:bg-teal-500/20">
      <TopAppBar />
      <main className="pt-20 px-4 md:px-12 max-w-5xl mx-auto space-y-6 pb-6">
        {/* Header Section */}
        <section className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h2 className="font-display text-2xl md:text-4xl font-bold tracking-tight text-slate-800 mb-1 md:mb-2">
              NeuroFlow <span className="text-teal-600">Dashboard</span>
            </h2>
            <p className="text-slate-500 text-base md:text-lg">
              Real-time monitoring and biometric analysis.
            </p>
          </div>
          <div className="hidden md:flex items-center gap-3 glass-panel px-5 py-2.5 rounded-full w-fit shadow-sm bg-white/80">
            <div className={`w-3 h-3 rounded-full shadow-inner ${connected ? 'bg-teal-500 animate-pulse-soft' : 'bg-rose-500'}`} />
            <span className="text-sm font-semibold tracking-wide text-slate-700">
              {connected ? "Device Connected" : "Device Offline"}
            </span>
            <span className="text-slate-300 mx-2">|</span>
            <Icon name="battery_full" className={battery < 20 ? "text-rose-500" : "text-teal-500"} />
            <span className="text-sm font-semibold text-slate-700">{battery}%</span>
          </div>
        </section>
   
        {/* Main Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Heart Rate Card */}
          <StatusCard 
            title="Heart Rate" 
            value={formatBpm(heartRate)} 
            unit="BPM" 
            icon="monitor_heart" 
            colorClass="text-rose-500 bg-rose-50"
            subtitle={telemetry ? "Real-time" : "Waiting"}
          >
            <div className="w-full h-16 flex items-end gap-1 mt-4 overflow-hidden rounded-md opacity-90 transition-opacity">
              {sparkline.map((height, i) => {
                const safeHeight = Math.max(8, Math.min(100, Number(height) || 8));
                return (
                  <div
                    key={i}
                    className={`flex-1 rounded-t-sm ${i === sparkline.length - 1 ? "bg-rose-400" : "bg-rose-200"}`}
                    style={{ height: `${safeHeight}%` }}
                  />
                );
              })}
            </div>
          </StatusCard>

          {/* Tremor Intensity Card */}
          <StatusCard 
            title="Tremor Intensity" 
            value={telemetry ? getTremorLabel(tremor) : "—"} 
            icon="vibration" 
            colorClass="text-amber-500 bg-amber-50"
            subtitle={telemetry ? getTremorStatus(tremor) : "Waiting"}
          >
            <div className="mt-4">
              <div className="w-full bg-slate-100 h-3 rounded-full overflow-hidden border border-slate-200 inset-shadow-sm">
                <div
                  className="bg-gradient-to-r from-teal-400 via-amber-400 to-rose-400 h-full rounded-full transition-all duration-1000 ease-out shadow-sm"
                  style={{ width: `${telemetry ? tremorToPercent(tremor) : 0}%` }}
                />
              </div>
              <div className="flex justify-between mt-2 text-[10px] uppercase font-bold tracking-wider text-slate-400">
                <span>Low</span>
                <span>Mod</span>
                <span>High</span>
              </div>
            </div>
          </StatusCard>

          {/* Stress Level Card */}
          <StatusCard 
            title="Stress Level" 
            value={telemetry ? `${stress}` : "—"} 
            unit="%"
            icon="psychology" 
            colorClass={`${stressColor} bg-slate-100`}
            subtitle={telemetry ? getStressLabel(stress) : "Waiting"}
          >
             <p className="text-sm mt-4 text-slate-500 font-medium leading-relaxed">
              {telemetry
                ? stress < 50
                  ? "Vitals indicate a relaxed state. Keep up the good work."
                  : stress < 75
                    ? "Slightly elevated stress. Consider a short break."
                    : "High stress detected. Recommended to start a breathing exercise."
                : "Awaiting sensor data..."}
            </p>
          </StatusCard>
        </div>

        {/* Action Section */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 glass-panel rounded-3xl p-8 relative overflow-hidden group border border-teal-100/50 shadow-sm bg-white/70">
            <div className="absolute top-0 right-0 p-12 opacity-5 group-hover:opacity-10 transition-opacity text-teal-600">
               <Icon name="air" className="text-9xl scale-150 rotate-12" />
            </div>
            <div className="relative z-10 max-w-md">
              <h3 className="font-display text-2xl font-bold mb-3 text-slate-800">Therapeutic Breathing</h3>
              <p className="text-slate-600 mb-8 leading-relaxed font-medium">
                Regulate your autonomic nervous system and lower stress levels through guided rhythmic breathing exercises.
              </p>
              <Link
                href="/breathe"
                className="inline-flex items-center gap-3 bg-teal-600 hover:bg-teal-500 text-white font-bold px-6 py-3 rounded-xl transition-all shadow-md hover:shadow-lg active:scale-95"
              >
                <span>Start Quick Calm</span>
                <Icon name="arrow_forward" />
              </Link>
            </div>
          </div>
          
          <div className="lg:col-span-1">
            <MotorPatternCard />
          </div>
        </section>
        
        {telemetry && <StressAlertPopup stressLevel={stress} />}
      </main>
    </div>
  );
}
