// @vitest-environment jsdom

import { render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"

const auth = vi.hoisted(() => ({
  getSession: vi.fn().mockRejectedValue(new Error("auth network unavailable")),
  onAuthStateChange: vi.fn(() => ({
    data: { subscription: { unsubscribe: vi.fn() } },
  })),
  signInWithPassword: vi.fn(),
  signOut: vi.fn(),
}))

vi.mock("@/lib/supabase", () => ({
  isSupabaseConfigured: true,
  supabase: { auth },
}))

import { AuthProvider } from "@/components/auth/AuthProvider"

it("recovers from a failed initial session lookup instead of loading forever", async () => {
  render(
    <AuthProvider>
      <div>Private portfolio</div>
    </AuthProvider>,
  )

  expect(await screen.findByRole("button", { name: "Sign in" })).toBeTruthy()
  expect(screen.queryByText("Checking your session…")).toBeNull()
})
