import type { CSSProperties } from "react"
import { Link } from "react-router-dom"

import { formatCurrency, formatDate, formatSignalName, formatSignalValue, riskTier, TRACKED_SIGNALS } from "@/lib/format"
import { cn, RISK_STYLES } from "@/lib/utils"
import type { Alert, AccountSummary, SignalSnapshot } from "@/types/api"

const STATUS_LABEL: Record<Alert["status"], string> = {
  open: "Open",
  acknowledged: "Acknowledged",
  resolved: "Resolved",
}

const STATUS_STEPS: Alert["status"][] = ["open", "acknowledged", "resolved"]
const STATUS_STEP_LABEL: Record<Alert["status"], string> = { open: "Open", acknowledged: "Acknowledged", resolved: "Resolved" }

// Open → Acknowledged → Resolved at a glance — reached steps bold (green once resolved), ahead steps muted.
function LifecycleStepper({ status }: { status: Alert["status"] }) {
  const currentIdx = STATUS_STEPS.indexOf(status)
  return (
    <div className="flex items-center" aria-label={`Alert status: ${STATUS_LABEL[status]}`}>
      {STATUS_STEPS.map((step, i) => {
        const reached = i <= currentIdx
        const dotClass = reached ? (status === "resolved" ? "bg-healthy" : "bg-ink") : "bg-neutral-300"
        return (
          <div key={step} className="flex items-center">
            <span className="flex items-center gap-1.5">
              <span className={cn("size-2 flex-none", dotClass)} />
              <span className={cn("text-[10px] uppercase tracking-[0.05em]", reached ? "font-extrabold text-neutral-800" : "font-semibold text-neutral-400")}>
                {STATUS_STEP_LABEL[step]}
              </span>
            </span>
            {i < STATUS_STEPS.length - 1 && <span className={cn("mx-1.5 h-px w-4 flex-none", i < currentIdx ? "bg-ink" : "bg-neutral-300")} />}
          </div>
        )
      })}
    </div>
  )
}

// Status moves freely both ways (backend/app/routers/alerts.py); forward moves (Acknowledge, Resolve) are solid red, undos are outline-only.
const STATUS_ACTIONS: Record<Alert["status"], Array<{ label: string; to: Alert["status"]; variant: "primary" | "secondary" }>> = {
  open: [{ label: "Acknowledge", to: "acknowledged", variant: "primary" }],
  acknowledged: [
    { label: "Unacknowledge", to: "open", variant: "secondary" },
    { label: "Resolve", to: "resolved", variant: "primary" },
  ],
  resolved: [{ label: "Reopen", to: "open", variant: "secondary" }],
}

const BUTTON_CLASS: Record<"primary" | "secondary", string> = {
  primary: "btn btn-primary",
  secondary: "btn btn-secondary",
}

interface AlertCardProps {
  alert: Alert
  account: AccountSummary | undefined
  latestSignals: SignalSnapshot | undefined
  style?: CSSProperties
  updating: boolean
  justUpdated: boolean
  onUpdateStatus: (alert: Alert, next: Alert["status"]) => void
}

// The single alert-card format shared by the Alerts inbox and Portfolio's "Latest alerts" preview.
export function AlertCard({ alert, account, latestSignals, style, updating, justUpdated, onUpdateStatus }: AlertCardProps) {
  const isResolved = alert.status === "resolved"
  const tier = riskTier(account?.composite_score ?? null)
  const tierStyle = RISK_STYLES[tier]
  const isUrgent = !isResolved && tier === "risk"

  return (
    <article
      style={style}
      className={cn(
        "animate-[row-in_280ms_cubic-bezier(0.16,1,0.3,1)_backwards] border-b border-l-[3px] border-r border-t border-b-divider border-r-divider border-t-divider transition-colors duration-700",
        isResolved ? "border-l-transparent bg-surface opacity-70" : cn(tierStyle.borderLeft, tierStyle.row),
        justUpdated && "!bg-ink/[0.08]",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-4 px-5 py-5">
        <div className="flex min-w-0 items-start gap-4">
          <div className="flex-none text-center">
            <div className={cn("text-[44px] font-extrabold leading-none tabular-nums", tierStyle.text)}>
              {account?.composite_score != null ? account.composite_score.toFixed(0) : "—"}
            </div>
            <div className="mt-1 text-[9.5px] font-extrabold uppercase tracking-[0.05em] text-neutral-600">Risk score</div>
          </div>

          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              {isUrgent && (
                <span className="relative flex size-2.5 flex-none" aria-hidden="true">
                  <span className="absolute inset-0 animate-ping rounded-full bg-risk opacity-75" />
                  <span className="relative size-2.5 rounded-full bg-risk" />
                </span>
              )}
              <Link to={`/accounts/${alert.account_id}`} className="text-[19px] font-extrabold tracking-[-0.02em] hover:text-accent-700">
                {alert.account_name ?? alert.account_id}
              </Link>
            </div>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
              <LifecycleStepper status={alert.status} />
              <span className="text-[12px] text-neutral-600">Flagged {formatDate(alert.triggered_at)}</span>
            </div>

            <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
              {alert.signals_fired.length > 0 && (
                <span className="text-[10px] font-extrabold uppercase tracking-[0.06em] text-neutral-500">Concerns</span>
              )}
              {alert.signals_fired.length > 0 ? (
                alert.signals_fired.map((signal) => (
                  <span key={signal} className="border border-divider px-1.5 py-[2px] text-[10.5px] font-semibold text-neutral-700">
                    {formatSignalName(signal)}
                  </span>
                ))
              ) : (
                <span className="text-[12px] text-neutral-700">No signals recorded</span>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-none gap-2">
          {STATUS_ACTIONS[alert.status].map((action) => (
            <button
              key={action.label}
              className={cn("flex-none", BUTTON_CLASS[action.variant])}
              disabled={updating}
              onClick={() => onUpdateStatus(alert, action.to)}
            >
              {updating ? "Updating…" : action.label}
            </button>
          ))}
        </div>
      </div>

      {latestSignals && (
        <div className="border-t border-divider px-5 py-4">
          <div className="text-[10.5px] font-extrabold uppercase tracking-[0.06em] text-neutral-600">
            Current stats — {formatDate(latestSignals.period_start)}
          </div>
          <div className="mt-2.5 flex flex-wrap items-center gap-x-7 gap-y-2.5">
            {TRACKED_SIGNALS.map((signal) => (
              <div key={signal} className="flex-none">
                <div className="text-[20px] font-extrabold leading-none tabular-nums">
                  {formatSignalValue(signal, latestSignals[signal] as number)}
                </div>
                <div className="mt-1 text-[10px] uppercase tracking-[0.04em] text-neutral-600">{formatSignalName(signal)}</div>
              </div>
            ))}
            {account && (
              <div className="ml-auto flex-none">
                <div className="text-[20px] font-extrabold leading-none tabular-nums">{formatCurrency(account.contract_value_monthly)}</div>
                <div className="mt-1 text-[10px] uppercase tracking-[0.04em] text-neutral-600">/mo contract</div>
              </div>
            )}
          </div>
        </div>
      )}

      {alert.suggested_action && (
        <div className="border-t border-divider px-5 py-4">
          <div className="text-[13px] font-extrabold">Recommended Action</div>
          <p className="mt-1 max-w-[70ch] text-[14px] leading-relaxed text-neutral-800">{alert.suggested_action}</p>
        </div>
      )}
    </article>
  )
}
