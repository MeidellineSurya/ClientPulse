import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Tailwind class sets per risk tier — the single source of colour truth for
// status anywhere in the app. Keyed on the backend's composite_score scale
// (higher = worse), not an inverted "health" scale.
export const RISK_STYLES = {
  healthy: { text: "text-healthy-ink", bg: "bg-healthy-tint", border: "border-transparent", borderLeft: "border-l-healthy", row: "" },
  watch: { text: "text-watch-ink", bg: "bg-watch-tint", border: "border-watch", borderLeft: "border-l-watch", row: "bg-watch/[0.05]" },
  risk: { text: "text-risk-ink", bg: "bg-risk-tint", border: "border-risk", borderLeft: "border-l-risk", row: "bg-risk/[0.05]" },
  unscored: { text: "text-neutral-600", bg: "bg-neutral-200", border: "border-transparent", borderLeft: "border-l-neutral-400", row: "" },
} as const

export const HEX = {
  healthy: "#4c8f68",
  watch: "#c07d10",
  risk: "#d8452a",
  unscored: "#9b9797",
  ink: "#201e1d",
  accent: "#ec3013",
} as const
