import type { ReactNode } from "react"

import { LoginForm } from "@/components/auth/LoginForm"
import { PasswordSetupForm } from "@/components/auth/PasswordSetupForm"

type AuthGateProps = {
  children: ReactNode
  configured: boolean
  loading: boolean
  signedIn: boolean
  requiresPasswordSetup: boolean
  onSignIn: (email: string, password: string) => Promise<void>
  onSetPassword: (password: string) => Promise<void>
}

export function AuthGate({
  children,
  configured,
  loading,
  signedIn,
  requiresPasswordSetup,
  onSignIn,
  onSetPassword,
}: AuthGateProps) {
  if (loading) {
    return (
      <main className="grid min-h-screen place-items-center bg-background text-sm text-muted-foreground">
        Checking your session…
      </main>
    )
  }

  if (!configured) {
    return (
      <main className="grid min-h-screen place-items-center bg-background px-6">
        <div className="max-w-md space-y-3 text-center">
          <p className="text-xl font-semibold">Authentication is not configured</p>
          <p className="text-sm text-muted-foreground">
            Add the public Supabase URL and anon key to the frontend environment.
          </p>
        </div>
      </main>
    )
  }

  if (!signedIn) {
    return (
      <main className="grid min-h-screen place-items-center bg-background px-6">
        <section className="w-full max-w-sm space-y-8">
          <header className="space-y-2">
            <p className="text-sm font-medium tracking-wide text-muted-foreground">
              CLIENTPULSE
            </p>
            <h1 className="text-3xl font-semibold tracking-tight">Welcome back</h1>
            <p className="text-sm text-muted-foreground">
              Sign in to open your agency’s retention workspace.
            </p>
          </header>
          <LoginForm onSignIn={onSignIn} />
        </section>
      </main>
    )
  }

  if (requiresPasswordSetup) {
    return <PasswordSetupForm onSetPassword={onSetPassword} />
  }

  return children
}
