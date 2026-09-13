// @vitest-environment jsdom

import { render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ listAccounts: vi.fn() }))
vi.mock("@/lib/api", () => ({
  api,
  ApiError: class ApiError extends Error {},
}))

import { Accounts } from "@/pages/Accounts"

it("shows a loading label instead of a false zero-account total", () => {
  api.listAccounts.mockReturnValue(new Promise(() => undefined))
  render(<Accounts />)

  expect(screen.getByText("Loading accounts…")).toBeTruthy()
  expect(screen.queryByText("0 of 0 accounts")).toBeNull()
})
