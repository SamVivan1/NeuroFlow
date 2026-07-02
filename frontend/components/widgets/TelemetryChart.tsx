"use client";

import { useTelemetry } from "@/context/TelemetryProvider";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine
} from "recharts";
import { Icon } from "@/components/Icon";
import { format } from "date-fns";

export function TelemetryChart() {
  const { history } = useTelemetry();

  if (!history || history.length === 0) {
    return (
      <div className="bg-white border border-slate-200 rounded-3xl p-6 h-[500px] flex flex-col items-center justify-center text-slate-400">
        <Icon name="show_chart" className="text-5xl mb-2 opacity-50" />
        <p className="text-sm font-medium">Awaiting telemetry data...</p>
      </div>
    );
  }

  // Format data for Recharts
  const chartData = history.map((point) => ({
    time: format(new Date(point.received_at), "HH:mm:ss"),
    hr: point.heart_rate > 0 ? point.heart_rate : null,
    tremor: point.tremor_intensity > 0 ? point.tremor_intensity : 0,
  }));

  return (
    <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-sm flex flex-col gap-8">
      <div className="flex items-center gap-2">
        <Icon name="monitoring" className="text-teal-600" />
        <h3 className="font-bold text-slate-800 text-lg">Real-Time Vitals</h3>
      </div>
      
      {/* Heart Rate Chart */}
      <div className="flex flex-col gap-2">
        <h4 className="text-sm font-semibold text-slate-500 ml-2">Heart Rate (BPM)</h4>
        <div className="h-[200px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 15, right: 20, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
              <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} minTickGap={40} />
              <YAxis domain={['dataMin - 10', 'dataMax + 10']} tick={{ fontSize: 11, fill: "#f43f5e" }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
              
              <ReferenceLine y={60} stroke="#10b981" strokeDasharray="3 3" label={{ position: 'insideTopLeft', value: 'Low (60)', fill: '#10b981', fontSize: 10 }} />
              <ReferenceLine y={100} stroke="#ef4444" strokeDasharray="3 3" label={{ position: 'insideTopLeft', value: 'High (100)', fill: '#ef4444', fontSize: 10 }} />
              
              <Line type="monotone" dataKey="hr" name="Heart Rate" stroke="#f43f5e" strokeWidth={3} dot={false} activeDot={{ r: 6, fill: "#f43f5e", stroke: "#fff", strokeWidth: 2 }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Tremor Intensity Chart */}
      <div className="flex flex-col gap-2">
        <h4 className="text-sm font-semibold text-slate-500 ml-2">Tremor Intensity (0-100)</h4>
        <div className="h-[200px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 15, right: 20, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
              <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} minTickGap={40} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#f59e0b" }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
              
              <ReferenceLine y={20} stroke="#10b981" strokeDasharray="3 3" label={{ position: 'insideTopLeft', value: 'Normal (<20)', fill: '#10b981', fontSize: 10 }} />
              <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="3 3" label={{ position: 'insideTopLeft', value: 'Severe (>70)', fill: '#ef4444', fontSize: 10 }} />
              
              <Line type="monotone" dataKey="tremor" name="Tremor" stroke="#f59e0b" strokeWidth={3} dot={false} activeDot={{ r: 6, fill: "#f59e0b", stroke: "#fff", strokeWidth: 2 }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
