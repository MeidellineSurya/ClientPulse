import { cn } from "@/lib/utils"

interface SegmentedProps<T extends string> {
  name: string
  options: readonly T[]
  value: T
  onChange: (value: T) => void
}

// Flush, zero-radius segmented control used for every filter in the app.
export function Segmented<T extends string>({ name, options, value, onChange }: SegmentedProps<T>) {
  return (
    <div className="flex flex-none flex-nowrap border border-divider">
      {options.map((opt) => (
        <label
          key={opt}
          className={cn(
            "cursor-pointer whitespace-nowrap border-r border-divider px-3 py-1.5 text-[12px] font-extrabold transition-colors duration-150 last:border-r-0",
            value === opt ? "bg-accent text-ground" : "hover:bg-ink/[0.06]",
          )}
        >
          <input type="radio" name={name} className="sr-only" checked={value === opt} onChange={() => onChange(opt)} />
          {opt}
        </label>
      ))}
    </div>
  )
}
