import { afterEach, describe, expect, it, vi } from "vitest"

import { api, setAccessTokenProvider } from "@/lib/api"

describe("authenticated API client", () => {
  afterEach(() => {
    setAccessTokenProvider(null)
    vi.unstubAllGlobals()
  })

  it("adds the current Supabase access token to protected requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    )
    vi.stubGlobal("fetch", fetchMock)
    setAccessTokenProvider(async () => "signed-access-token")

    await api.listAccounts()

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer signed-access-token",
      },
    })
  })

  it("does not issue a protected request without an access token", async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal("fetch", fetchMock)
    setAccessTokenProvider(async () => null)

    await expect(api.listAccounts()).rejects.toMatchObject({ status: 401 })
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
