import { useEffect, useMemo, useState, type ReactNode } from "react"
import type { Session } from "@supabase/supabase-js"

import { AuthGate } from "@/components/auth/AuthGate"
import { AuthContext, type AuthState } from "@/components/auth/auth-context"
import { setAccessTokenProvider } from "@/lib/api"
import { isSupabaseConfigured, supabase } from "@/lib/supabase"

function isPasswordSetupCallback() {
  if (typeof window === "undefined") return false
  const query = new URLSearchParams(window.location.search)
  const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""))
  const type = query.get("type") ?? hash.get("type")
  return type === "invite" || type === "recovery"
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [requiresPasswordSetup, setRequiresPasswordSetup] = useState(
    isPasswordSetupCallback,
  )

  useEffect(() => {
    if (!supabase) {
      setAccessTokenProvider(null)
      setLoading(false)
      return
    }

    let active = true
    const applySession = (nextSession: Session | null) => {
      if (!active) return
      setAccessTokenProvider(async () => nextSession?.access_token ?? null)
      setSession(nextSession)
      setLoading(false)
    }
    void (async () => {
      try {
        const { data } = await supabase.auth.getSession()
        applySession(data.session)
      } catch {
        applySession(null)
      }
    })()
    const { data } = supabase.auth.onAuthStateChange((event, nextSession) => {
      if (event === "PASSWORD_RECOVERY") setRequiresPasswordSetup(true)
      applySession(nextSession)
    })

    return () => {
      active = false
      setAccessTokenProvider(null)
      data.subscription.unsubscribe()
    }
  }, [])

  async function signIn(email: string, password: string) {
    if (!supabase) {
      throw new Error("Authentication is not configured")
    }
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
  }

  async function signOut() {
    if (!supabase) return
    const { error } = await supabase.auth.signOut()
    if (error) throw error
  }

  async function setPassword(password: string) {
    if (!supabase) throw new Error("Authentication is not configured")
    const { error } = await supabase.auth.updateUser({ password })
    if (error) throw error
    window.history.replaceState({}, document.title, window.location.pathname)
    setRequiresPasswordSetup(false)
  }

  const value = useMemo<AuthState>(
    () => ({ email: session?.user.email ?? null, signOut }),
    [session],
  )

  return (
    <AuthContext.Provider value={value}>
      <AuthGate
        configured={isSupabaseConfigured}
        loading={loading}
        signedIn={session !== null}
        requiresPasswordSetup={requiresPasswordSetup}
        onSignIn={signIn}
        onSetPassword={setPassword}
      >
        {children}
      </AuthGate>
    </AuthContext.Provider>
  )
}
