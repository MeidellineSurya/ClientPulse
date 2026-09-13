// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react"
import { useEffect, useState } from "react"
import { afterEach, expect, it, vi } from "vitest"

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
import { api, setAccessTokenProvider } from "@/lib/api"

afterEach(() => {
  cleanup()
  setAccessTokenProvider(null)
  vi.unstubAllGlobals()
})

it("recovers from a failed initial session lookup instead of loading forever", async () => {
  render(
    <AuthProvider>
      <div>Private portfolio</div>
    </AuthProvider>,
  )

  expect(await screen.findByRole("button", { name: "Sign in" })).toBeTruthy()
  expect(screen.queryByText("Checking your session…")).toBeNull()
})

it("installs the restored token before authenticated children request data", async () => {
  auth.getSession.mockResolvedValueOnce({
    data: {
      session: {
        access_token: "restored-token",
        user: { email: "owner@example.com" },
      },
    },
  })
  const fetchMock = vi.fn().mockResolvedValue(
    new Response("[]", {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  )
  vi.stubGlobal("fetch", fetchMock)

  function DataConsumer() {
    const [loaded, setLoaded] = useState(false)
    useEffect(() => {
      void api.listAccounts().then(() => setLoaded(true))
    }, [])
    return <div>{loaded ? "Portfolio loaded" : "Portfolio pending"}</div>
  }

  render(
    <AuthProvider>
      <DataConsumer />
    </AuthProvider>,
  )

  expect(await screen.findByText("Portfolio loaded")).toBeTruthy()
  expect(fetchMock).toHaveBeenCalledWith(
    expect.any(String),
    expect.objectContaining({
      headers: expect.objectContaining({ Authorization: "Bearer restored-token" }),
    }),
  )
})
