import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Tailwind class sets per risk tier — the single source of colour truth for status anywhere in the app.
export const RISK_STYLES = {
  healthy: { text: "text-healthy-ink", bg: "bg-healthy-tint", border: "border-transparent", borderLeft: "border-l-healthy", row: "" },
  watch: { text: "text-watch-ink", bg: "bg-watch-tint", border: "border-watch", borderLeft: "border-l-watch", row: "bg-watch/[0.05]" },
  risk: { text: "text-risk-ink", bg: "bg-risk-tint", border: "border-risk", borderLeft: "border-l-risk", row: "bg-risk/[0.08]" },
  unscored: { text: "text-neutral-600", bg: "bg-neutral-200", border: "border-transparent", borderLeft: "border-l-neutral-400", row: "" },
} as const

export const HEX = {
  healthy: "#4c8f68",
  watch: "#c07d10",
  risk: "#d8452a",
  unscored: "#9b9797",
  ink: "#201e1d",
  accent: "#9c2a12",
} as const

// Closest item in a time series to a target timestamp — a best-effort proximity join, not an exact match.
export function nearestByDate<T>(items: T[], targetIso: string, getIso: (item: T) => string): T | null {
  if (items.length === 0) return null
  const targetTime = new Date(targetIso).getTime()
  return items.reduce<T | null>((best, item) => {
    if (!best) return item
    const itemDelta = Math.abs(new Date(getIso(item)).getTime() - targetTime)
    const bestDelta = Math.abs(new Date(getIso(best)).getTime() - targetTime)
    return itemDelta < bestDelta ? item : best
  }, null)
}
