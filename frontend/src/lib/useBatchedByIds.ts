import { useEffect, useState } from "react"

export interface BatchedByIds<T> {
  data: Record<string, T>
  loading: boolean
}

interface BatchState<T> extends BatchedByIds<T> {
  key: string
}

type BatchFetcher<T> = () => Promise<Record<string, T>>
const activeBatches = new WeakMap<BatchFetcher<unknown>, Promise<Record<string, unknown>>>()

async function fetchWithRetry<T>(fetcher: BatchFetcher<T>): Promise<Record<string, T>> {
  try {
    return await fetcher()
  } catch {
    await new Promise((resolve) => window.setTimeout(resolve, 100))
    return fetcher()
  }
}

function sharedBatch<T>(fetcher: BatchFetcher<T>): Promise<Record<string, T>> {
  const key = fetcher as BatchFetcher<unknown>
  const existing = activeBatches.get(key)
  if (existing) return existing as Promise<Record<string, T>>

  const promise = fetchWithRetry(fetcher)
  activeBatches.set(key, promise as Promise<Record<string, unknown>>)
  void promise.then(
    () => {
      if (activeBatches.get(key) === promise) activeBatches.delete(key)
    },
    () => {
      if (activeBatches.get(key) === promise) activeBatches.delete(key)
    },
  )
  return promise
}

// Loads one agency-scoped batch and projects it onto the IDs required by the
// caller. The active flag prevents an older navigation request from replacing
// data for a newer ID set.
export function useBatchedByIds<T>(
  ids: string[],
  fetcher: () => Promise<Record<string, T>>,
): BatchedByIds<T> {
  const key = ids.join("\u0000")
  const [state, setState] = useState<BatchState<T>>({
    key,
    data: {},
    loading: ids.length > 0,
  })

  useEffect(() => {
    if (!key) {
      setState({ key, data: {}, loading: false })
      return
    }

    let active = true
    const requestedIds = key.split("\u0000")
    setState({ key, data: {}, loading: true })
    sharedBatch(fetcher)
      .then((allValues) => {
        if (!active) return
        const data: Record<string, T> = {}
        for (const id of requestedIds) {
          if (id in allValues) data[id] = allValues[id]
        }
        setState({ key, data, loading: false })
      })
      .catch(() => {
        if (active) setState({ key, data: {}, loading: false })
      })

    return () => {
      active = false
    }
  }, [fetcher, key])

  if (state.key !== key) return { data: {}, loading: ids.length > 0 }
  return { data: state.data, loading: state.loading }
}
