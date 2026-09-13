// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { expect, it, vi } from "vitest"

import { LoginForm } from "@/components/auth/LoginForm"

it("submits email and password to the authentication adapter", async () => {
  const signIn = vi.fn().mockResolvedValue(undefined)
  render(<LoginForm onSignIn={signIn} />)

  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "owner@agency.example" },
  })
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "safe-password" },
  })
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }))

  await waitFor(() => {
    expect(signIn).toHaveBeenCalledWith("owner@agency.example", "safe-password")
  })
})
