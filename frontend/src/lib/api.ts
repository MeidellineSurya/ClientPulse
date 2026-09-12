import type { AccountDetail, AccountSummary, Alert, HealthScorePoint, SignalSnapshot } from "@/types/api"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
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
  getAccountHealthHistory: (id: string) => request<HealthScorePoint[]>(`/accounts/${id}/health-history`),
  listAlerts: () => request<Alert[]>("/alerts"),
  setAlertStatus: (id: string, status: Alert["status"]) =>
    request<Alert>(`/alerts/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    }),
}

export { ApiError }
