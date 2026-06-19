"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@/components/Icon";

const NAV_ITEMS = [
  { href: "/", label: "Dash", icon: "monitor_heart" },
  { href: "/breathe", label: "Breathe", icon: "air" },
  { href: "/reports", label: "Reports", icon: "query_stats" },
  { href: "/settings", label: "Settings", icon: "settings" },
] as const;

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 w-full z-50 flex justify-around items-center px-4 pb-4 pt-2 bg-surface shadow-[0_-4px_12px_rgba(0,0,0,0.05)]">
      {NAV_ITEMS.map(({ href, label, icon }) => {
        const active = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            className={`flex flex-col items-center justify-center rounded-xl px-4 py-2 min-h-touch-target-min active:scale-90 transition-all duration-200 ${
              active
                ? "bg-secondary-container text-on-secondary-container"
                : "text-on-surface-variant hover:bg-surface-container-high"
            }`}
          >
            <Icon name={icon} filled={active} />
            <span className="text-label-lg font-semibold tracking-wide">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
