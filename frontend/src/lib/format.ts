// Small display helpers. computeRevenueAtRisk mirrors
// backend/app/services/scoring_engine.py's compute_revenue_at_risk exactly
// (annualized contract value x composite_score/100) — duplicated here only
// because /accounts doesn't currently return it, so the portfolio table can
// still show a number consistent with what /score/recompute would report.

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value)
}

export function computeRevenueAtRisk(contractValueMonthly: number, compositeScore: number | null): number {
  if (compositeScore === null) return 0
  return contractValueMonthly * 12 * (compositeScore / 100)
}

export type HealthTier = "healthy" | "watch" | "at-risk" | "unscored"

export function healthTier(score: number | null): HealthTier {
  if (score === null) return "unscored"
  if (score >= 60) return "at-risk"
  if (score >= 30) return "watch"
  return "healthy"
}

export const healthTierStyles: Record<HealthTier, string> = {
  healthy: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  watch: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  "at-risk": "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
  unscored: "bg-muted text-muted-foreground",
}

export const severityStyles: Record<string, string> = {
  low: "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  high: "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-300",
  critical: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
}

export function formatSignalName(signal: string): string {
  return signal
    .split("_")
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(" ")
}
