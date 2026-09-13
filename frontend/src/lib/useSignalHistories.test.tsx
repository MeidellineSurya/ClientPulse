// @vitest-environment jsdom

import { act, renderHook, waitFor } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({
  getAccountSignals: vi.fn(),
  listSignalHistories: vi.fn(),
}))

vi.mock("@/lib/api", () => ({ api }))

import { useSignalHistories } from "@/lib/useSignalHistories"

afterEach(() => vi.resetAllMocks())

it("retries one transient batch failure instead of publishing empty history", async () => {
  api.listSignalHistories
    .mockRejectedValueOnce(new Error("temporary read failure"))
    .mockResolvedValueOnce({ a: [{ period_start: "2026-01-01" }] })

  const { result } = renderHook(() => useSignalHistories(["a"]))

  await waitFor(() => expect(result.current.loading).toBe(false))
  expect(api.listSignalHistories).toHaveBeenCalledTimes(2)
  expect(result.current.data.a).toHaveLength(1)
})

it("loads all requested histories with one batch request", async () => {
  let resolveBatch: (value: Record<string, Array<{ period_start: string }>>) => void = () => undefined
  api.listSignalHistories.mockReturnValue(
    new Promise((resolve) => {
      resolveBatch = resolve
    }),
  )

  const { result } = renderHook(() => useSignalHistories(["a", "b"]))
  expect(result.current.loading).toBe(true)
  expect(result.current.data).toEqual({})
  expect(api.listSignalHistories).toHaveBeenCalledTimes(1)
  expect(api.getAccountSignals).not.toHaveBeenCalled()

  await act(async () => {
    resolveBatch({ a: [{ period_start: "2026-01-01" }], b: [{ period_start: "2026-01-08" }] })
  })

  await waitFor(() => expect(result.current.loading).toBe(false))
  expect(Object.keys(result.current.data)).toEqual(["a", "b"])
})
