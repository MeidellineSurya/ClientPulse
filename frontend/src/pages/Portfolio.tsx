import { ArrowDown, ArrowUp, Minus } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api, ApiError } from "@/lib/api"
import { computeRevenueAtRisk, formatCurrency, formatDate, healthTier, healthTierStyles } from "@/lib/format"
import type { AccountSummary } from "@/types/api"

type SortKey = "composite_score" | "name" | "contract_value_monthly"

function TrendArrow({ slope }: { slope: number | null }) {
  if (slope === null || Math.abs(slope) < 0.5) return <Minus className="size-4 text-muted-foreground" />
  return slope > 0 ? (
    <ArrowUp className="size-4 text-red-600" />
  ) : (
    <ArrowDown className="size-4 text-emerald-600" />
  )
}

export function Portfolio() {
  const [accounts, setAccounts] = useState<AccountSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>("composite_score")

  useEffect(() => {
    api
      .listAccounts()
      .then(setAccounts)
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : "Failed to load accounts")
      })
  }, [])

  const sorted = useMemo(() => {
    if (!accounts) return []
    return [...accounts].sort((a, b) => {
      if (sortKey === "name") return a.name.localeCompare(b.name)
      if (sortKey === "contract_value_monthly") return b.contract_value_monthly - a.contract_value_monthly
      return (b.composite_score ?? -1) - (a.composite_score ?? -1)
    })
  }, [accounts, sortKey])

  const totalAtRiskRevenue = useMemo(
    () =>
      sorted
        .filter((a) => (a.composite_score ?? 0) >= 60)
        .reduce((sum, a) => sum + computeRevenueAtRisk(a.contract_value_monthly, a.composite_score), 0),
    [sorted],
  )

  const atRiskCount = sorted.filter((a) => (a.composite_score ?? 0) >= 60).length

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Portfolio</h1>
        <p className="text-sm text-muted-foreground">Every account, sorted by churn risk.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total accounts</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{accounts?.length ?? "—"}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Accounts at risk</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold text-red-600">{atRiskCount}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total revenue at risk</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold text-red-600">
            {formatCurrency(totalAtRiskRevenue)}
          </CardContent>
        </Card>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Couldn't load accounts: {error}
        </div>
      )}

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead
                className="cursor-pointer select-none"
                onClick={() => setSortKey("name")}
              >
                Account
              </TableHead>
              <TableHead
                className="cursor-pointer select-none"
                onClick={() => setSortKey("contract_value_monthly")}
              >
                Contract value
              </TableHead>
              <TableHead
                className="cursor-pointer select-none"
                onClick={() => setSortKey("composite_score")}
              >
                Health score
              </TableHead>
              <TableHead>Trend</TableHead>
              <TableHead>Last scored</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((account) => {
              const tier = healthTier(account.composite_score)
              return (
                <TableRow key={account.id}>
                  <TableCell className="font-medium">
                    <Link to={`/accounts/${account.id}`} className="hover:underline">
                      {account.name}
                    </Link>
                  </TableCell>
                  <TableCell>{formatCurrency(account.contract_value_monthly)}/mo</TableCell>
                  <TableCell>
                    <Badge variant="secondary" className={healthTierStyles[tier]}>
                      {account.composite_score !== null ? account.composite_score.toFixed(0) : "—"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <TrendArrow slope={account.trend_slope} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {account.health_computed_at ? formatDate(account.health_computed_at) : "Never scored"}
                  </TableCell>
                </TableRow>
              )
            })}
            {accounts !== null && sorted.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">
                  No accounts yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
