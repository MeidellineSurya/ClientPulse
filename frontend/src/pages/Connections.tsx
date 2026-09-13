import { useEffect, useRef, useState } from "react"
import { Calendar, FileSpreadsheet, Mail } from "lucide-react"

import { api, ApiError } from "@/lib/api"
import { formatSignalName } from "@/lib/format"
import type { CsvIngestResult, GoogleIntegrationStatus } from "@/types/api"

type SyncProgress = { done: number; total: number; current: string }
type SyncResult = { succeeded: number; failed: number }

export function Connections() {
  const [googleStatus, setGoogleStatus] = useState<GoogleIntegrationStatus | null>(null)
  const [googleStatusError, setGoogleStatusError] = useState<string | null>(null)

  const [syncing, setSyncing] = useState(false)
  const [syncProgress, setSyncProgress] = useState<SyncProgress | null>(null)
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null)
  const [syncError, setSyncError] = useState<string | null>(null)

  const [csvUploading, setCsvUploading] = useState(false)
  const [csvResult, setCsvResult] = useState<CsvIngestResult | null>(null)
  const [csvError, setCsvError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api
      .getGoogleIntegrationStatus()
      .then(setGoogleStatus)
      .catch((err: unknown) => setGoogleStatusError(err instanceof ApiError ? err.message : "Couldn't check connection"))
  }, [])

  async function syncAllAccounts() {
    setSyncing(true)
    setSyncError(null)
    setSyncResult(null)
    try {
      const accounts = await api.listAccounts()
      let succeeded = 0
      let failed = 0
      for (const [index, account] of accounts.entries()) {
        setSyncProgress({ done: index, total: accounts.length, current: account.name })
        try {
          await api.syncGmailCalendar(account.id)
          succeeded += 1
        } catch {
          failed += 1
        }
      }
      setSyncResult({ succeeded, failed })
    } catch (err) {
      setSyncError(err instanceof ApiError ? err.message : "Sync failed")
    } finally {
      setSyncing(false)
      setSyncProgress(null)
    }
  }

  async function handleCsvSelected(file: File) {
    setCsvUploading(true)
    setCsvError(null)
    setCsvResult(null)
    try {
      setCsvResult(await api.uploadInvoiceCsv(file))
    } catch (err) {
      setCsvError(err instanceof ApiError ? err.message : "Upload failed")
    } finally {
      setCsvUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ""
    }
  }

  const googleConnected = googleStatus?.connected ?? false
  const connectedCount = (googleConnected ? 2 : 0) + 1 // Gmail + Calendar share one connection; CSV needs no setup

  return (
    <div>
      <header className="rule px-10 pb-6 pt-8">
        <h1 className="text-[32px] tracking-[-0.03em]">Connections</h1>
        <p className="mt-1.5 max-w-[64ch] text-[13.5px] text-neutral-700">
          ClientPulse reads metadata only: timestamps, attendee counts and invoice dates. Message content is never read or stored.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <span className="text-[13px] font-extrabold tabular-nums">{connectedCount} of 3 sources active</span>
          <div className="flex gap-1.5">
            <span className={googleConnected ? "size-2.5 bg-healthy" : "size-2.5 bg-neutral-400"} aria-hidden="true" />
            <span className={googleConnected ? "size-2.5 bg-healthy" : "size-2.5 bg-neutral-400"} aria-hidden="true" />
            <span className="size-2.5 bg-healthy" aria-hidden="true" />
          </div>
        </div>
      </header>

      <div className="grid gap-4 px-10 pb-12 pt-6 [grid-template-columns:repeat(auto-fit,minmax(280px,1fr))]">
        {/* Gmail */}
        <div className="flex flex-col border border-divider p-5">
          <div className="flex items-start justify-between gap-3">
            <Mail size={22} className="text-neutral-600" />
            <StatusBadge loading={!googleStatus && !googleStatusError} connected={googleConnected} />
          </div>
          <div className="mt-2.5 text-[16px] font-extrabold">Gmail</div>
          <p className="mt-1 text-[12.5px] leading-snug text-neutral-700">
            Pulls response-time signals from metadata only — message bodies are never read.
          </p>
          <SignalTags signals={["avg_response_time_hours"]} />
          <p className="mt-3 text-[11px] leading-snug text-neutral-600">
            Reads timestamps and participant counts only. Message subject and body are never read or stored.
          </p>
          <div className="mt-auto pt-4">
            <button
              className="btn btn-secondary w-full justify-center"
              disabled={!googleConnected || syncing}
              onClick={syncAllAccounts}
            >
              {syncing ? "Syncing…" : "Sync all accounts"}
            </button>
            <SyncStatusLine
              googleStatusError={googleStatusError}
              googleDetail={googleStatus?.detail ?? null}
              syncing={syncing}
              syncProgress={syncProgress}
              syncResult={syncResult}
              syncError={syncError}
            />
          </div>
        </div>

        {/* Calendar */}
        <div className="flex flex-col border border-divider p-5">
          <div className="flex items-start justify-between gap-3">
            <Calendar size={22} className="text-neutral-600" />
            <StatusBadge loading={!googleStatus && !googleStatusError} connected={googleConnected} />
          </div>
          <div className="mt-2.5 text-[16px] font-extrabold">Google Calendar</div>
          <p className="mt-1 text-[12.5px] leading-snug text-neutral-700">
            Pulls meeting frequency and cancellation signals from the connected calendar.
          </p>
          <SignalTags signals={["meetings_scheduled", "meetings_cancelled"]} />
          <p className="mt-3 text-[11px] leading-snug text-neutral-600">
            Reads event timestamps and attendee counts only. Event titles and descriptions are never read or stored.
          </p>
          <div className="mt-auto pt-4">
            <button className="btn btn-secondary w-full justify-center" disabled title="Synced together with Gmail — see that card">
              Synced with Gmail
            </button>
            <p className="mt-1.5 text-center text-[11px] text-neutral-600">
              One Google connection powers both Gmail and Calendar.
            </p>
          </div>
        </div>

        {/* CSV */}
        <div className="flex flex-col border border-divider p-5">
          <div className="flex items-start justify-between gap-3">
            <FileSpreadsheet size={22} className="text-neutral-600" />
            <span className="border border-healthy bg-healthy-tint px-2 py-[3px] text-[10px] font-extrabold uppercase tracking-[0.05em] text-healthy-ink">
              Ready
            </span>
          </div>
          <div className="mt-2.5 text-[16px] font-extrabold">CSV Upload</div>
          <p className="mt-1 text-[12.5px] leading-snug text-neutral-700">
            Upload invoice/payment history to compute the payment-lag signal.
          </p>
          <SignalTags signals={["invoice_days_late"]} />
          <p className="mt-3 text-[11px] leading-snug text-neutral-600">
            A stand-in for a live accounting integration (e.g. Xero) until one is built. Columns:
            account_email, invoice_date, due_date, paid_date.
          </p>
          <div className="mt-auto pt-4">
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              id="csv-upload-input"
              onChange={(event) => {
                const file = event.target.files?.[0]
                if (file) void handleCsvSelected(file)
              }}
            />
            <button
              className="btn btn-secondary w-full justify-center"
              disabled={csvUploading}
              onClick={() => fileInputRef.current?.click()}
            >
              {csvUploading ? "Uploading…" : "Upload CSV"}
            </button>
            <CsvStatusLine result={csvResult} error={csvError} />
          </div>
        </div>
      </div>
    </div>
  )
}

function StatusBadge({ loading, connected }: { loading: boolean; connected: boolean }) {
  if (loading) {
    return (
      <span className="border border-divider px-2 py-[3px] text-[10px] font-extrabold uppercase tracking-[0.05em] text-neutral-500">
        Checking…
      </span>
    )
  }
  return (
    <span
      className={
        connected
          ? "border border-healthy bg-healthy-tint px-2 py-[3px] text-[10px] font-extrabold uppercase tracking-[0.05em] text-healthy-ink"
          : "border border-divider px-2 py-[3px] text-[10px] font-extrabold uppercase tracking-[0.05em] text-neutral-600"
      }
    >
      {connected ? "Connected" : "Not connected"}
    </span>
  )
}

function SignalTags({ signals }: { signals: string[] }) {
  return (
    <div className="mt-3.5 flex flex-wrap items-center gap-1.5">
      <span className="text-[10px] font-extrabold uppercase tracking-[0.05em] text-neutral-500">Powers</span>
      {signals.map((signal) => (
        <span key={signal} className="border border-divider bg-surface px-1.5 py-[2px] text-[10.5px] font-semibold text-neutral-700">
          {formatSignalName(signal)}
        </span>
      ))}
    </div>
  )
}

function SyncStatusLine({
  googleStatusError,
  googleDetail,
  syncing,
  syncProgress,
  syncResult,
  syncError,
}: {
  googleStatusError: string | null
  googleDetail: string | null
  syncing: boolean
  syncProgress: SyncProgress | null
  syncResult: SyncResult | null
  syncError: string | null
}) {
  if (syncing && syncProgress) {
    return (
      <p className="mt-1.5 text-center text-[11px] text-neutral-600">
        Syncing {syncProgress.done + 1} of {syncProgress.total} — {syncProgress.current}
      </p>
    )
  }
  if (syncError) {
    return <p className="mt-1.5 text-center text-[11px] text-risk-ink">{syncError}</p>
  }
  if (syncResult) {
    return (
      <p className="mt-1.5 text-center text-[11px] text-neutral-600">
        Synced {syncResult.succeeded} account{syncResult.succeeded === 1 ? "" : "s"}
        {syncResult.failed > 0 ? `, ${syncResult.failed} failed` : ""}
      </p>
    )
  }
  if (googleStatusError) {
    return <p className="mt-1.5 text-center text-[11px] text-risk-ink">{googleStatusError}</p>
  }
  if (googleDetail) {
    return <p className="mt-1.5 text-center text-[11px] text-neutral-600">{googleDetail}</p>
  }
  return <p className="mt-1.5 text-center text-[11px] text-neutral-600">Pulls the current week for every account.</p>
}

function CsvStatusLine({ result, error }: { result: CsvIngestResult | null; error: string | null }) {
  if (error) {
    return <p className="mt-1.5 text-center text-[11px] text-risk-ink">{error}</p>
  }
  if (result) {
    return (
      <p className="mt-1.5 text-center text-[11px] text-neutral-600">
        Parsed {result.rows_parsed}/{result.rows_received}, updated {result.snapshots_updated}
        {result.unmatched.length > 0 ? `, ${result.unmatched.length} unmatched` : ""}
        {result.rows_failed > 0 ? `, ${result.rows_failed} failed` : ""}
      </p>
    )
  }
  return <p className="mt-1.5 text-center text-[11px] text-neutral-600">account_email, invoice_date, due_date, paid_date</p>
}
