import React from "react";
import { Icon } from "@/components/Icon";

interface StatusCardProps {
  title: string;
  value: string | number;
  unit?: string;
  icon: string;
  colorClass?: string;
  subtitle?: string;
  children?: React.ReactNode;
}

export function StatusCard({
  title,
  value,
  unit,
  icon,
  colorClass = "text-teal-600 bg-teal-50",
  subtitle,
  children,
}: StatusCardProps) {
  return (
    <div className="glass-panel bg-white/80 p-6 rounded-2xl flex flex-col gap-4 shadow-sm border border-slate-200/60 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-3 rounded-xl shadow-sm ${colorClass}`}>
            <Icon name={icon} className="text-2xl" />
          </div>
          <h3 className="font-display font-semibold text-slate-700">{title}</h3>
        </div>
        {subtitle && (
          <span className="text-xs font-bold px-3 py-1 rounded-full bg-slate-100 text-slate-500 tracking-wide uppercase">
            {subtitle}
          </span>
        )}
      </div>

      <div className="flex items-baseline gap-2 mt-2">
        <span className="font-display text-4xl font-bold tracking-tight text-slate-800">
          {value}
        </span>
        {unit && <span className="text-slate-500 font-semibold">{unit}</span>}
      </div>

      {children && <div className="mt-2">{children}</div>}
    </div>
  );
}
