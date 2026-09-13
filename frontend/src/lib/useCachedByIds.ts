import { useEffect, useState } from "react"

// Cap on simultaneous in-flight requests — avoids firing a request-per-account burst that can exhaust the backend's connection pool.
const MAX_CONCURRENT = 6

// Module-scoped so every hook instance sharing a cacheKey shares one cache and one in-flight set, not one each.
const caches = new Map<string, Map<string, unknown>>()
const inFlight = new Map<string, Set<string>>()

function cacheFor<T>(cacheKey: string): Map<string, T> {
  let cache = caches.get(cacheKey) as Map<string, T> | undefined
  if (!cache) {
    cache = new Map()
    caches.set(cacheKey, cache)
  }
  return cache
}

function inFlightFor(cacheKey: string): Set<string> {
  let flying = inFlight.get(cacheKey)
  if (!flying) {
    flying = new Set()
    inFlight.set(cacheKey, flying)
  }
  return flying
}

// Fetches `fetcher(id)` once per id across every caller of this cacheKey, throttled to MAX_CONCURRENT in flight.
export function useCachedByIds<T>(cacheKey: string, ids: string[], fetcher: (id: string) => Promise<T>): Record<string, T> {
  const cache = cacheFor<T>(cacheKey)
  const flying = inFlightFor(cacheKey)
  const [, bump] = useState(0)

  useEffect(() => {
    const pending = ids.filter((id) => !cache.has(id) && !flying.has(id))
    if (pending.length === 0) return

    let cursor = 0
    async function worker() {
      while (cursor < pending.length) {
        const id = pending[cursor++]
        flying.add(id)
        try {
          const value = await fetcher(id)
          cache.set(id, value)
          bump((n) => n + 1)
        } catch {
          // Non-fatal: that id just stays absent from the returned record.
        } finally {
          flying.delete(id)
        }
      }
    }

    const workerCount = Math.min(MAX_CONCURRENT, pending.length)
    for (let i = 0; i < workerCount; i++) worker()
    // No cleanup needed — fetches are cached module-wide and outlive this effect on purpose.
  }, [ids, cache, flying, fetcher])

  const result: Record<string, T> = {}
  for (const id of ids) {
    if (cache.has(id)) result[id] = cache.get(id) as T
  }
  return result
}
