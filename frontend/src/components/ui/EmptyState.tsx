interface EmptyStateProps {
  title: string
  body: string
}

export function EmptyState({ title, body }: EmptyStateProps) {
  return (
    <div className="border border-dashed border-divider p-12 text-center">
      <div className="text-[16px] font-extrabold">{title}</div>
      <div className="mt-1 text-[13px] text-neutral-700">{body}</div>
    </div>
  )
}
