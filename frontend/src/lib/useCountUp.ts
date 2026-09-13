import { useEffect, useRef, useState } from "react"

// Animates 0 -> value once on mount (cubic ease-out); jumps straight to value under prefers-reduced-motion.
export function useCountUp(value: number, durationMs = 900): number {
  const [display, setDisplay] = useState(0)
  const target = useRef(value)
  target.current = value

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setDisplay(target.current)
      return
    }
    let frame: number
    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs)
      const eased = 1 - Math.pow(1 - t, 3)
      setDisplay(target.current * eased)
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return display
}
