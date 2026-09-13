// @vitest-environment jsdom

import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"

import { useCountUp } from "@/lib/useCountUp"

beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false } as MediaQueryList)))
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) =>
    window.setTimeout(() => callback(performance.now()), 16),
  )
  vi.stubGlobal("cancelAnimationFrame", (id: number) => window.clearTimeout(id))
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

it("starts a fresh count when data arrives after the initial zero animation completed", () => {
  const { result, rerender } = renderHook(({ value }) => useCountUp(value, 100), {
    initialProps: { value: 0 },
  })

  act(() => {
    vi.advanceTimersByTime(150)
  })
  expect(result.current).toBe(0)

  rerender({ value: 48 })
  act(() => {
    vi.advanceTimersByTime(150)
  })

  expect(result.current).toBe(48)
})
