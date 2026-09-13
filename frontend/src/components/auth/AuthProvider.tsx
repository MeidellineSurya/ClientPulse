import { useEffect, useMemo, useState, type ReactNode } from "react"
import type { Session } from "@supabase/supabase-js"

import { AuthGate } from "@/components/auth/AuthGate"
import { AuthContext, type AuthState } from "@/components/auth/auth-context"
import { setAccessTokenProvider } from "@/lib/api"
import { isSupabaseConfigured, supabase } from "@/lib/supabase"

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!supabase) {
      setLoading(false)
      return
    }

    let active = true
    void (async () => {
      try {
        const { data } = await supabase.auth.getSession()
        if (active) setSession(data.session)
      } catch {
        if (active) setSession(null)
      } finally {
        if (active) setLoading(false)
      }
    })()
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      if (active) {
        setSession(nextSession)
        setLoading(false)
      }
    })

    return () => {
      active = false
      data.subscription.unsubscribe()
    }
  }, [])

  useEffect(() => {
    setAccessTokenProvider(async () => session?.access_token ?? null)
    return () => setAccessTokenProvider(null)
  }, [session])

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
        onSignIn={signIn}
      >
        {children}
      </AuthGate>
    </AuthContext.Provider>
  )
}
