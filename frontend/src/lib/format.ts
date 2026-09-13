// Small display helpers. computeRevenueAtRisk mirrors backend's compute_revenue_at_risk since /accounts doesn't return it directly.

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

// Same cut points as backend/app/services/scoring_engine.py — composite_score is a risk score, higher is worse.
export function riskTier(score: number | null): RiskTier {
  if (score === null) return "unscored"
  if (score >= 60) return "risk"
  if (score >= 30) return "watch"
  return "healthy"
}

// Solid fills (not tints) so these badges stay visible on top of severity-tinted card backgrounds.
export const severityStyles: Record<string, string> = {
  low: "bg-neutral-300 text-neutral-800",
  medium: "bg-watch text-ground",
  high: "bg-risk text-ground",
  critical: "bg-accent text-ground",
}

// Mirrors backend HIGHER_IS_WORSE — meetings_scheduled is the odd one out, a drop is the risk direction.
export const HIGHER_IS_WORSE: Partial<Record<string, boolean>> = {
  avg_response_time_hours: true,
  meetings_cancelled: true,
  invoice_days_late: true,
  meetings_scheduled: false,
}

export type SignalStatus = "good" | "watch" | "bad"

// Colour-codes a value against that same account's own history (mean/stddev), never a fixed universal threshold.
export function signalStatus(signal: string, value: number, allValues: number[]): SignalStatus {
  if (allValues.length < 2) return "watch"
  const mean = allValues.reduce((sum, v) => sum + v, 0) / allValues.length
  const variance = allValues.reduce((sum, v) => sum + (v - mean) ** 2, 0) / allValues.length
  const stddev = Math.sqrt(variance)
  const higherIsWorse = HIGHER_IS_WORSE[signal] ?? true
  const delta = higherIsWorse ? value - mean : mean - value
  if (stddev === 0) return delta > 0 ? "watch" : "good"
  const z = delta / stddev
  if (z >= 1) return "bad"
  if (z > 0.15) return "watch"
  return "good"
}

export const SIGNAL_STATUS_TEXT: Record<SignalStatus, string> = {
  good: "text-healthy-ink",
  watch: "text-watch-ink",
  bad: "text-risk-ink",
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
}

// Overrides where the generic split-and-capitalize reads awkwardly (the unit is already shown via formatSignalValue).
const SIGNAL_LABEL_OVERRIDE: Record<string, string> = {
  avg_response_time_hours: "Avg Response Time",
}

export function formatSignalName(signal: string): string {
  return (
    SIGNAL_LABEL_OVERRIDE[signal] ??
    signal
      .split("_")
      .map((w) => w[0].toUpperCase() + w.slice(1))
      .join(" ")
  )
}

const SIGNAL_UNIT: Partial<Record<string, (v: number) => string>> = {
  avg_response_time_hours: (v) => `${v.toFixed(1)}h`,
  invoice_days_late: (v) => `${v.toFixed(0)}d`,
}

// Single source of signal-value formatting so every chart's ticks/tooltips stay in sync.
export function formatSignalValue(signal: string, value: number): string {
  return (SIGNAL_UNIT[signal] ?? ((v: number) => v.toFixed(0)))(value)
}

// contact_changed is a point-in-time flag, not a continuous metric, so it's excluded from this trend-history list.
export const TRACKED_SIGNALS = ["avg_response_time_hours", "meetings_cancelled", "invoice_days_late", "meetings_scheduled"] as const

// Product policy, not backend-enforced — the bar the UI holds a score to before treating it as trustworthy.
export const MIN_DATA_COVERAGE_DAYS = 90

export interface DataCoverage {
  days: number
  isSufficient: boolean
  daysRemaining: number
}

// Real span of an account's actual signal_snapshot history — never a fabricated or assumed number.
export function computeDataCoverage(history: Array<{ period_start: string; period_end: string }>): DataCoverage {
  if (history.length === 0) {
    return { days: 0, isSufficient: false, daysRemaining: MIN_DATA_COVERAGE_DAYS }
  }
  const start = new Date(history[0].period_start).getTime()
  const end = new Date(history[history.length - 1].period_end).getTime()
  const days = Math.max(0, Math.round((end - start) / 86_400_000))
  return {
    days,
    isSufficient: days >= MIN_DATA_COVERAGE_DAYS,
    daysRemaining: Math.max(0, MIN_DATA_COVERAGE_DAYS - days),
  }
}
