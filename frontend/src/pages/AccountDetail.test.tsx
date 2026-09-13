// @vitest-environment jsdom

import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { afterEach, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({
  getAccount: vi.fn(),
  getAccountHealthHistory: vi.fn(),
}))

vi.mock("@/lib/api", () => ({
  api,
  ApiError: class ApiError extends Error {},
}))

vi.mock("recharts", () => ({
  Line: ({ type, dot }: { type: string; dot?: unknown }) => (
    <i data-testid="chart-line" data-line-type={type} data-has-dots={String(Boolean(dot))} />
  ),
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ReferenceLine: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}))

import { AccountDetail } from "@/pages/AccountDetail"

const ACCOUNT_ID = "11111111-1111-4111-8111-111111111111"

function snapshot(index: number, email: string) {
  const period = new Date(Date.UTC(2026, 0, 1 + index * 7)).toISOString().slice(0, 10)
  return {
    period_start: period,
    period_end: period,
    avg_response_time_hours: 3 + (index % 4),
    meetings_scheduled: 2 + (index % 3),
    meetings_cancelled: index % 4,
    invoice_days_late: index % 5,
    primary_contact_email: email,
  }
}

const history = [
  ...Array.from({ length: 6 }, (_, index) => snapshot(index, "first@acme.com")),
  ...Array.from({ length: 6 }, (_, index) => snapshot(index + 6, "second@acme.com")),
  ...Array.from({ length: 6 }, (_, index) => snapshot(index + 12, "third@acme.com")),
  ...Array.from({ length: 8 }, (_, index) => snapshot(index + 18, "fourth@acme.com")),
]

afterEach(() => {
  vi.clearAllMocks()
})

it("renders real contact transitions as a three-event graph beside every numeric signal", async () => {
  api.getAccount.mockResolvedValue({
    id: ACCOUNT_ID,
    name: "Acme",
    contract_value_monthly: 10000,
    contract_start_date: "2025-01-01",
    primary_contact_email: "fourth@acme.com",
    composite_score: 52,
    trend_slope: 4,
    health_computed_at: "2026-01-26T00:00:00Z",
    signal_history: history,
    contact_events: [
      {
        period_end: "2026-02-12",
        previous_contact_email: "first@acme.com",
        current_contact_email: "second@acme.com",
      },
      {
        period_end: "2026-03-26",
        previous_contact_email: "second@acme.com",
        current_contact_email: "third@acme.com",
      },
      {
        period_end: "2026-05-07",
        previous_contact_email: "third@acme.com",
        current_contact_email: "fourth@acme.com",
      },
    ],
    alerts: [],
    contact_changed_at: "2026-05-07",
    previous_contact_email: "third@acme.com",
  })
  api.getAccountHealthHistory.mockResolvedValue([
    { composite_score: 24, trend_slope: -2, computed_at: "2026-01-12T00:00:00Z" },
    { composite_score: 36, trend_slope: 3, computed_at: "2026-01-19T00:00:00Z" },
    { composite_score: 52, trend_slope: 4, computed_at: "2026-01-26T00:00:00Z" },
  ])

  render(
    <MemoryRouter initialEntries={[`/accounts/${ACCOUNT_ID}`]}>
      <Routes>
        <Route path="/accounts/:id" element={<AccountDetail />} />
      </Routes>
    </MemoryRouter>,
  )

  expect(await screen.findByRole("heading", { name: "Contact changes" })).toBeTruthy()
  expect(screen.getByText("3 changes across 26 reporting periods")).toBeTruthy()
  expect(screen.getByLabelText("Contact change events over time")).toBeTruthy()
  expect(screen.getAllByTestId("contact-event-marker")).toHaveLength(3)
  expect(screen.getByText(/first@acme.com → second@acme.com/)).toBeTruthy()
  expect(screen.getByText(/third@acme.com → fourth@acme.com/)).toBeTruthy()
  const chartLines = screen.getAllByTestId("chart-line")
  expect(chartLines).toHaveLength(5)
  expect(chartLines.every((line) => line.dataset.lineType === "linear")).toBe(true)
  expect(chartLines.every((line) => line.dataset.hasDots === "true")).toBe(true)
})
