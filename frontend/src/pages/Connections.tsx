import { Calendar, FileSpreadsheet, Mail } from "lucide-react"

const CONNECTIONS = [
  {
    icon: Mail,
    title: "Gmail",
    description: "Pulls response-time and thread-count signals from metadata only — message bodies are never read.",
  },
  {
    icon: Calendar,
    title: "Google Calendar",
    description: "Pulls meeting frequency and cancellation signals from the connected calendar.",
  },
  {
    icon: FileSpreadsheet,
    title: "CSV Upload",
    description: "Upload invoice/payment history to compute the payment-lag signal.",
  },
]

export function Connections() {
  return (
    <div>
      <header className="rule px-10 pb-6 pt-8">
        <h1 className="text-[32px] tracking-[-0.03em]">Connections</h1>
        <p className="mt-1.5 max-w-[64ch] text-[13.5px] text-neutral-700">
          ClientPulse reads metadata only — timestamps, attendee counts and invoice dates. Message content is never read or stored.
        </p>
      </header>

      <div className="grid gap-4 px-10 pb-12 pt-6 [grid-template-columns:repeat(auto-fit,minmax(240px,1fr))]">
        {CONNECTIONS.map((connection) => (
          <div key={connection.title} className="border border-divider p-5">
            <connection.icon size={22} className="text-neutral-600" />
            <div className="mt-2.5 text-[16px] font-extrabold">{connection.title}</div>
            <p className="mt-1 text-[12.5px] leading-snug text-neutral-700">{connection.description}</p>
            <button className="btn btn-secondary mt-4 w-full justify-center" disabled>
              Connect (not wired up yet)
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
