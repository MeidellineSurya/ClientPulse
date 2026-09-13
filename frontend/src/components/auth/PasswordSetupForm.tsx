import { useState, type FormEvent } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

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
    <main className="grid min-h-screen place-items-center bg-background px-6">
      <section className="w-full max-w-sm space-y-8">
        <header className="space-y-2">
          <p className="text-sm font-medium tracking-wide text-muted-foreground">
            CLIENTPULSE
          </p>
          <h1 className="text-3xl font-semibold tracking-tight">Set your password</h1>
          <p className="text-sm text-muted-foreground">
            Finish accepting your invitation to open the StudioCo workspace.
          </p>
        </header>
        <form className="space-y-5" onSubmit={submit}>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="new-password">
              New password
            </label>
            <Input
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
            <Input
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
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          ) : null}
          <Button className="w-full" type="submit" disabled={submitting}>
            {submitting ? "Setting password…" : "Set password"}
          </Button>
        </form>
      </section>
    </main>
  )
}
