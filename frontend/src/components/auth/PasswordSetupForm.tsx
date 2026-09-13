import { useState, type FormEvent } from "react"

type PasswordSetupFormProps = {
  onSetPassword: (password: string) => Promise<void>
}

export function PasswordSetupForm({ onSetPassword }: PasswordSetupFormProps) {
  const [password, setPassword] = useState("")
  const [confirmation, setConfirmation] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    if (password.length < 8) {
      setError("Password must be at least 8 characters")
      return
    }
    if (password !== confirmation) {
      setError("Passwords do not match")
      return
    }
    setSubmitting(true)
    try {
      await onSetPassword(password)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not set password")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-ground px-6">
      <section className="w-full max-w-sm space-y-8">
        <header className="space-y-2">
          <p className="text-sm font-extrabold tracking-[0.1em] text-neutral-600">
            CLIENTPULSE
          </p>
          <h1 className="text-3xl font-semibold tracking-tight">Set your password</h1>
          <p className="text-sm text-neutral-600">
            Finish accepting your invitation to open the StudioCo workspace.
          </p>
        </header>
        <form className="space-y-5" onSubmit={submit}>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="new-password">
              New password
            </label>
            <input
              className="w-full border-2 border-divider bg-ground px-3 py-2 text-sm outline-none focus:border-ink"
              id="new-password"
              type="password"
              autoComplete="new-password"
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="confirm-password">
              Confirm password
            </label>
            <input
              className="w-full border-2 border-divider bg-ground px-3 py-2 text-sm outline-none focus:border-ink"
              id="confirm-password"
              type="password"
              autoComplete="new-password"
              minLength={8}
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              required
            />
          </div>
          {error ? (
            <p className="text-sm text-risk" role="alert">
              {error}
            </p>
          ) : null}
          <button
            className="w-full bg-ink px-4 py-2.5 text-sm font-extrabold text-ground disabled:opacity-50"
            type="submit"
            disabled={submitting}
          >
            {submitting ? "Setting password…" : "Set password"}
          </button>
        </form>
      </section>
    </main>
  )
}
