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

export type RiskTier = "healthy" | "watch" | "risk" | "unscored"

// Same cut points as RISK_ALERT_THRESHOLD (60) and the severity bands in
// backend/app/services/scoring_engine.py — composite_score is a risk score,
// higher is worse.
export function riskTier(score: number | null): RiskTier {
  if (score === null) return "unscored"
  if (score >= 60) return "risk"
  if (score >= 30) return "watch"
  return "healthy"
}

export const severityStyles: Record<string, string> = {
  low: "bg-neutral-200 text-neutral-800",
  medium: "bg-watch-tint text-watch-ink",
  high: "bg-risk-tint text-risk-ink",
  critical: "bg-accent text-ground",
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
