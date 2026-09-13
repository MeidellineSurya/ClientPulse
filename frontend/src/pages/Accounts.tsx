import { useEffect, useMemo, useState } from "react"

import { AccountTable } from "@/components/AccountTable"
import { Loading } from "@/components/ui/Loading"
import { Segmented } from "@/components/ui/Segmented"
import { api, ApiError } from "@/lib/api"
import { riskTier } from "@/lib/format"
import type { AccountSummary } from "@/types/api"

const FILTERS = ["All", "At risk", "Watch", "Healthy"] as const
type Filter = (typeof FILTERS)[number]

const FILTER_TIER: Record<Exclude<Filter, "All">, ReturnType<typeof riskTier>> = {
  "At risk": "risk",
  Watch: "watch",
  Healthy: "healthy",
}

export function Accounts() {
  const [accounts, setAccounts] = useState<AccountSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState("")
  const [filter, setFilter] = useState<Filter>("All")

  useEffect(() => {
    api
      .listAccounts()
      .then(setAccounts)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Failed to load accounts"))
  }, [])

  const rows = useMemo(() => {
    if (!accounts) return []
    const q = query.trim().toLowerCase()
    return accounts.filter((a) => {
      const matchesQuery = !q || a.name.toLowerCase().includes(q)
      const matchesFilter = filter === "All" || riskTier(a.composite_score) === FILTER_TIER[filter]
      return matchesQuery && matchesFilter
    })
  }, [accounts, query, filter])

  return (
    <div>
      <header className="rule px-10 pb-5 pt-7">
        <h1 className="text-[32px] tracking-[-0.03em]">Accounts</h1>
        <p className="mt-1 text-[13.5px] text-neutral-700">Every account, scored against its own baseline. Click a row to see why.</p>
      </header>

      {error && (
        <div className="border-b border-divider bg-risk-tint px-10 py-3 text-[13px] text-risk-ink">Couldn't load accounts: {error}</div>
      )}

      <div className="flex flex-wrap items-center gap-3 border-b border-divider px-10 py-3.5">
        <input
          className="w-full max-w-[420px] flex-1 border border-divider bg-transparent px-3 py-1.5 text-[13px] placeholder:text-neutral-600"
          placeholder="Search clients"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <Segmented name="account-filter" options={FILTERS} value={filter} onChange={setFilter} />
        <div className="ml-auto text-[12.5px] text-neutral-700">
          {rows.length} of {accounts?.length ?? 0} accounts
        </div>
      </div>

      <div className="px-10 pb-11 pt-5">{accounts ? <AccountTable accounts={rows} /> : <Loading rows={10} />}</div>
    </div>
  )
}
