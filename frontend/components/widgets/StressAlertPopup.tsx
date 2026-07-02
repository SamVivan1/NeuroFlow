import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";

interface StressAlertPopupProps {
  stressLevel: number;
}

export function StressAlertPopup({ stressLevel }: StressAlertPopupProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [hasDismissed, setHasDismissed] = useState(false);
  const router = useRouter();

  useEffect(() => {
    let redirectTimer: NodeJS.Timeout;

    if (stressLevel > 75 && !hasDismissed) {
      setIsVisible(true);
      // Auto-redirect after 2 seconds
      redirectTimer = setTimeout(() => {
        router.push("/breathe");
      }, 2000);
    } else {
      setIsVisible(false);
    }

    return () => clearTimeout(redirectTimer);
  }, [stressLevel, hasDismissed, router]);

  if (!isVisible) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom-5 fade-in duration-300">
      <div className="bg-white p-5 rounded-2xl shadow-2xl border border-rose-100 flex flex-col gap-3 w-80 relative overflow-hidden">
        {/* Soft background pulse */}
        <div className="absolute -top-10 -right-10 w-24 h-24 bg-rose-100/50 rounded-full blur-2xl animate-pulse-soft"></div>
        
        <div className="flex items-start justify-between relative z-10">
          <div className="flex items-center gap-2 text-rose-500 font-bold">
            <Icon name="warning" />
            <span>High Stress Detected</span>
          </div>
          <button 
            onClick={() => setHasDismissed(true)}
            className="text-slate-400 hover:text-slate-600 transition-colors"
          >
            <Icon name="close" className="text-xl" />
          </button>
        </div>
        
        <p className="text-slate-600 text-sm font-medium relative z-10">
          Your stress level is at {stressLevel}%. Take a moment to reset your nervous system.
        </p>

        <div className="mt-2 relative z-10">
          <Link
            href="/breathe"
            className="block w-full text-center bg-rose-500 hover:bg-rose-400 text-white font-bold py-2 rounded-xl transition-colors shadow-sm"
          >
            Start Breathing Guide
          </Link>
        </div>
      </div>
    </div>
  );
}
