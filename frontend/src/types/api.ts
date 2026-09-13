// Mirrors backend/app/schemas.py. Kept as plain interfaces (not generated)
// since the backend doesn't currently publish an OpenAPI-derived client —
// if these two ever drift, the failure mode is a TS type error against the
// fetch response shape, not a silent runtime bug.

export interface AccountSummary {
  id: string
  name: string
  contract_value_monthly: number
  composite_score: number | null
  trend_slope: number | null
  health_computed_at: string | null
}

export interface SignalSnapshot {
  period_start: string
  period_end: string
  avg_response_time_hours: number
  meetings_scheduled: number
  meetings_cancelled: number
  invoice_days_late: number
  primary_contact_email: string | null
}

export interface ContactChangeEvent {
  period_end: string
  previous_contact_email: string
  current_contact_email: string
}

export interface HealthScorePoint {
  composite_score: number
  trend_slope: number
  computed_at: string
}

export interface Alert {
  id: string
  account_id: string
  account_name: string | null
  triggered_at: string
  signals_fired: string[]
  severity: string
  ai_brief: string | null
  suggested_action: string | null
  status: "open" | "acknowledged" | "resolved"
}

export interface AccountDetail {
  id: string
  name: string
  contract_value_monthly: number
  contract_start_date: string
  primary_contact_email: string | null
  composite_score: number | null
  trend_slope: number | null
  health_computed_at: string | null
  signal_history: SignalSnapshot[]
  contact_events: ContactChangeEvent[]
  alerts: Alert[]
  contact_changed_at: string | null
  previous_contact_email: string | null
}
