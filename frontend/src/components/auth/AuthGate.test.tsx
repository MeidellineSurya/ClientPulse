// @vitest-environment jsdom

import { render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"

import { AuthGate } from "@/components/auth/AuthGate"

it("does not render protected application content without a session", () => {
  render(
    <AuthGate
      configured
      loading={false}
      signedIn={false}
      onSignIn={vi.fn()}
    >
      <div>Private portfolio</div>
    </AuthGate>,
  )

  expect(screen.queryByText("Private portfolio")).toBeNull()
  expect(screen.getByRole("button", { name: "Sign in" })).toBeTruthy()
})

it("renders protected application content for an authenticated session", () => {
  render(
    <AuthGate
      configured
      loading={false}
      signedIn
      onSignIn={vi.fn()}
    >
      <div>Private portfolio</div>
    </AuthGate>,
  )

  expect(screen.getByText("Private portfolio")).toBeTruthy()
})
