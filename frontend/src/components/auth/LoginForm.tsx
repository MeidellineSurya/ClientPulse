import { useState, type FormEvent } from "react"

type LoginFormProps = {
  onSignIn: (email: string, password: string) => Promise<void>
}

export function LoginForm({ onSignIn }: LoginFormProps) {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await onSignIn(email.trim(), password)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sign in failed")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="space-y-5" onSubmit={submit}>
      <div className="space-y-2">
        <label className="text-sm font-medium" htmlFor="email">
          Email
        </label>
        <input
          className="w-full border-2 border-divider bg-ground px-3 py-2 text-sm outline-none focus:border-ink"
          id="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium" htmlFor="password">
          Password
        </label>
        <input
          className="w-full border-2 border-divider bg-ground px-3 py-2 text-sm outline-none focus:border-ink"
          id="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
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
        {submitting ? "Signing in…" : "Sign in"}
      </button>
    </form>
  )
}
