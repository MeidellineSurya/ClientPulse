import { useEffect, useRef, useState } from "react"

// Animates each newly loaded value from the value currently on screen. Delayed
// API responses therefore restart the animation instead of leaving a completed
// zero-value animation stuck forever.
export function useCountUp(value: number, durationMs = 900): number {
  const [display, setDisplay] = useState(0)
  const displayRef = useRef(0)

  useEffect(() => {
    const setCurrent = (next: number) => {
      displayRef.current = next
      setDisplay(next)
    }

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || durationMs <= 0) {
      setCurrent(value)
      return
    }

    let frame: number
    const from = displayRef.current
    const startedAt = performance.now()
    const tick = (now: number) => {
      const progress = Math.min(1, (now - startedAt) / durationMs)
      const eased = 1 - Math.pow(1 - progress, 3)
      setCurrent(from + (value - from) * eased)
      if (progress < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [durationMs, value])

  return display
}
