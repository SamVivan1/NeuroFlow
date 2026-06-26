import type { CSSProperties, ReactNode } from "react";

interface IconProps {
  name: string;
  filled?: boolean;
  className?: string;
  style?: CSSProperties;
}

export function Icon({ name, filled = false, className = "", style }: IconProps) {
  return (
    <span
      className={`material-symbols-outlined ${filled ? "filled" : ""} ${className}`}
      style={style}
    >
      {name}
    </span>
  );
}
