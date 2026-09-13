import type { ReactNode } from "react"

interface EmptyStateProps {
  title: string
  body: string
  extra?: ReactNode
}

export function EmptyState({ title, body, extra }: EmptyStateProps) {
  return (
    <div className="border border-dashed border-divider p-12 text-center">
      <div className="text-[16px] font-extrabold">{title}</div>
      <div className="mx-auto mt-1 max-w-[46ch] text-[13px] text-neutral-700">{body}</div>
      {extra}
    </div>
  )
}
