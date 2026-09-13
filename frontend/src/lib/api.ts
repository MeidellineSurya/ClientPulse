import type { AccountDetail, AccountSummary, Alert, HealthScorePoint, SignalSnapshot } from "@/types/api"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"
type AccessTokenProvider = () => Promise<string | null>

let accessTokenProvider: AccessTokenProvider | null = null

export function setAccessTokenProvider(provider: AccessTokenProvider | null) {
  accessTokenProvider = provider
}

class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await accessTokenProvider?.()
  if (!token) {
    throw new ApiError(401, "Authentication required")
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers as Record<string, string> | undefined),
      Authorization: `Bearer ${token}`,
    },
  })
  if (!response.ok) {
    const body = await response.text().catch(() => "")
    throw new ApiError(response.status, body || response.statusText)
  }
  return response.json() as Promise<T>
}

export const api = {
  listAccounts: () => request<AccountSummary[]>("/accounts"),
  getAccount: (id: string) => request<AccountDetail>(`/accounts/${id}`),
  getAccountSignals: (id: string) => request<SignalSnapshot[]>(`/accounts/${id}/signals`),
  listSignalHistories: () => request<Record<string, SignalSnapshot[]>>("/accounts/signal-histories"),
  getAccountHealthHistory: (id: string) => request<HealthScorePoint[]>(`/accounts/${id}/health-history`),
  listHealthHistories: () => request<Record<string, HealthScorePoint[]>>("/accounts/health-histories"),
  listAlerts: () => request<Alert[]>("/alerts"),
  setAlertStatus: (id: string, status: Alert["status"]) =>
    request<Alert>(`/alerts/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    }),
}

export { ApiError }
