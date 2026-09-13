import { Calendar, FileSpreadsheet, Mail } from "lucide-react"

import { formatSignalName } from "@/lib/format"

// connected is always false today (real state, none wired up yet); signals lists the real SignalSnapshot fields each feeds.
const CONNECTIONS = [
  {
    icon: Mail,
    title: "Gmail",
    description: "Pulls response-time signals from metadata only — message bodies are never read.",
    scope: "Reads timestamps and participant counts only. Message subject and body are never read or stored.",
    signals: ["avg_response_time_hours"],
    connected: false,
  },
  {
    icon: Calendar,
    title: "Google Calendar",
    description: "Pulls meeting frequency and cancellation signals from the connected calendar.",
    scope: "Reads event timestamps and attendee counts only. Event titles and descriptions are never read or stored.",
    signals: ["meetings_scheduled", "meetings_cancelled"],
    connected: false,
  },
  {
    icon: FileSpreadsheet,
    title: "CSV Upload",
    description: "Upload invoice/payment history to compute the payment-lag signal.",
    scope: "A stand-in for a live accounting integration (e.g. Xero) until one is built.",
    signals: ["invoice_days_late"],
    connected: false,
  },
]

const connectedCount = CONNECTIONS.filter((c) => c.connected).length

export function Connections() {
  return (
    <div>
      <header className="rule px-10 pb-6 pt-8">
        <h1 className="text-[32px] tracking-[-0.03em]">Connections</h1>
        <p className="mt-1.5 max-w-[64ch] text-[13.5px] text-neutral-700">
          ClientPulse reads metadata only: Timestamps, attendee counts and invoice dates. Message content is never read or stored.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <span className="text-[13px] font-extrabold tabular-nums">
            {connectedCount} of {CONNECTIONS.length} sources connected
          </span>
          <div className="flex gap-1.5">
            {CONNECTIONS.map((c) => (
              <span key={c.title} className={c.connected ? "size-2.5 bg-healthy" : "size-2.5 bg-neutral-400"} aria-hidden="true" />
            ))}
          </div>
        </div>
      </header>

      <div className="grid gap-4 px-10 pb-12 pt-6 [grid-template-columns:repeat(auto-fit,minmax(280px,1fr))]">
        {CONNECTIONS.map((connection) => (
          <div key={connection.title} className="flex flex-col border border-divider p-5">
            <div className="flex items-start justify-between gap-3">
              <connection.icon size={22} className="text-neutral-600" />
              <span
                className={
                  connection.connected
                    ? "border border-healthy bg-healthy-tint px-2 py-[3px] text-[10px] font-extrabold uppercase tracking-[0.05em] text-healthy-ink"
                    : "border border-divider px-2 py-[3px] text-[10px] font-extrabold uppercase tracking-[0.05em] text-neutral-600"
                }
              >
                {connection.connected ? "Connected" : "Not connected"}
              </span>
            </div>

            <div className="mt-2.5 text-[16px] font-extrabold">{connection.title}</div>
            <p className="mt-1 text-[12.5px] leading-snug text-neutral-700">{connection.description}</p>

            <div className="mt-3.5 flex flex-wrap items-center gap-1.5">
              <span className="text-[10px] font-extrabold uppercase tracking-[0.05em] text-neutral-500">Powers</span>
              {connection.signals.map((signal) => (
                <span key={signal} className="border border-divider bg-surface px-1.5 py-[2px] text-[10.5px] font-semibold text-neutral-700">
                  {formatSignalName(signal)}
                </span>
              ))}
            </div>

            <p className="mt-3 text-[11px] leading-snug text-neutral-600">{connection.scope}</p>

            <div className="mt-auto pt-4">
              <button className="btn btn-secondary w-full justify-center" disabled>
                Connect
              </button>
              <p className="mt-1.5 text-center text-[11px] text-neutral-600">Integration coming soon</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
