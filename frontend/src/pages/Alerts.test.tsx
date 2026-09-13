// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({
  listAlerts: vi.fn(),
  listAccounts: vi.fn(),
  listSignalHistories: vi.fn(),
  setAlertStatus: vi.fn(),
}))

vi.mock("@/lib/api", () => ({
  api,
  ApiError: class ApiError extends Error {},
}))

import { Alerts } from "@/pages/Alerts"

const ALERT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
const ACCOUNT_ID = "11111111-1111-4111-8111-111111111111"
const initialAlert = {
  id: ALERT_ID,
  account_id: ACCOUNT_ID,
  account_name: "Acme",
  triggered_at: "2026-09-10T00:00:00+00:00",
  signals_fired: ["meetings_cancelled"],
  severity: "high",
  ai_brief: null,
  suggested_action: null,
  status: "open" as const,
}

afterEach(() => {
  vi.clearAllMocks()
})

it("keeps the account name visible after an alert is acknowledged then resolved", async () => {
  api.listAlerts.mockResolvedValue([initialAlert])
  api.listAccounts.mockResolvedValue([])
  api.setAlertStatus
    .mockResolvedValueOnce({ ...initialAlert, account_name: null, status: "acknowledged" })
    .mockResolvedValueOnce({ ...initialAlert, account_name: null, status: "resolved" })

  render(
    <MemoryRouter>
      <Alerts />
    </MemoryRouter>,
  )

  expect(await screen.findByRole("link", { name: "Acme" })).toBeTruthy()

  fireEvent.click(screen.getByRole("button", { name: "Acknowledge" }))
  expect(await screen.findByRole("button", { name: "Resolve" })).toBeTruthy()
  expect(screen.getByRole("link", { name: "Acme" })).toBeTruthy()

  fireEvent.click(screen.getByRole("button", { name: "Resolve" }))
  expect(await screen.findByLabelText("Alert status: Resolved")).toBeTruthy()
  expect(screen.getByRole("link", { name: "Acme" })).toBeTruthy()
  expect(screen.queryByText(ACCOUNT_ID)).toBeNull()
})
