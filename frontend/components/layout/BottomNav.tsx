"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@/components/Icon";

export function BottomNav() {
  const pathname = usePathname();

  const navItems = [
    { name: "Dash", path: "/", icon: "dashboard" },
    { name: "Breathe", path: "/breathe", icon: "air" },
    { name: "Reports", path: "/reports", icon: "monitoring" },
    { name: "Settings", path: "/settings", icon: "settings" },
  ];

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white/90 backdrop-blur-md border-t border-slate-200 z-50 pb-safe">
      <div className="flex justify-around items-center h-16 px-2">
        {navItems.map((item) => {
          const isActive = pathname === item.path;
          return (
            <Link
              key={item.name}
              href={item.path}
              className={`flex flex-col items-center justify-center w-full h-full gap-1 transition-colors ${
                isActive ? "text-teal-600" : "text-slate-400 hover:text-slate-600"
              }`}
            >
              <div
                className={`flex items-center justify-center w-12 h-8 rounded-full transition-all ${
                  isActive ? "bg-teal-100/50" : ""
                }`}
              >
                <Icon
                  name={item.icon}
                  filled={isActive}
                  className={`text-xl ${isActive ? "scale-110" : ""}`}
                />
              </div>
              <span className={`text-[10px] font-semibold tracking-wide ${isActive ? "font-bold" : ""}`}>
                {item.name}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
