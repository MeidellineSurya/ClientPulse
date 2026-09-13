interface LoadingProps {
  rows?: number
}

// Skeleton rows — keeps the ruled rhythm while data resolves.
export function Loading({ rows = 6 }: LoadingProps) {
  return (
    <div className="animate-pulse">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 border-b border-divider py-3.5">
          <div className="h-4 w-1/4 bg-neutral-300" />
          <div className="h-4 w-16 bg-neutral-200" />
          <div className="h-4 w-10 bg-neutral-200" />
          <div className="h-4 flex-1 bg-neutral-200" />
        </div>
      ))}
    </div>
  )
}
