import { Activity, LayoutDashboard, LogOut, Plug, TriangleAlert, Users } from "lucide-react"
import { useEffect, useState } from "react"
import { NavLink, Outlet, useLocation } from "react-router-dom"

import { useAuth } from "@/components/auth/auth-context"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"

const NAV_ITEMS = [
  { to: "/", label: "Portfolio", end: true, icon: LayoutDashboard },
  { to: "/accounts", label: "Accounts", end: false, icon: Users },
  { to: "/alerts", label: "Alerts", end: false, icon: TriangleAlert },
  { to: "/connections", label: "Connections", end: false, icon: Plug },
]

export function AppLayout() {
  const [openAlerts, setOpenAlerts] = useState(0)
  const { email, signOut } = useAuth()
  const location = useLocation()

  useEffect(() => {
    api
      .listAlerts()
      .then((alerts) => setOpenAlerts(alerts.filter((a) => a.status === "open").length))
      .catch(() => {
        // Non-fatal: the nav badge just stays at 0 if this fails.
      })
  }, [])

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-[212px] flex-none flex-col border-r-2 border-divider">
        <div className="flex items-center gap-2 border-b-2 border-divider px-[18px] py-5">
          <Activity size={20} strokeWidth={2.2} className="text-accent" />
          <span className="text-[17px] font-extrabold tracking-[-0.03em]">ClientPulse</span>
        </div>

        <nav className="flex flex-col py-2.5">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "flex items-center justify-between border-l-[3px] px-[18px] py-2.5 text-[13px] font-extrabold transition-colors duration-150",
                  isActive
                    ? "border-accent bg-ink/[0.08] text-ink"
                    : "border-transparent text-neutral-700 hover:bg-ink/[0.06]",
                )
              }
            >
              <span className="flex items-center gap-2.5">
                <item.icon size={18} strokeWidth={2.2} />
                {item.label}
              </span>
              {item.label === "Alerts" && openAlerts > 0 && (
                <span className="bg-accent px-1.5 text-[10px] font-extrabold text-ground">
                  {openAlerts}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto border-t-2 border-divider p-[18px]">
          <p className="truncate text-[11px] font-bold text-neutral-600">{email}</p>
          <button
            className="mt-2 flex items-center gap-2 text-[12px] font-extrabold text-neutral-700 hover:text-ink"
            type="button"
            onClick={() => void signOut()}
          >
            <LogOut size={14} />
            Sign out
          </button>
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        <div key={location.pathname} className="animate-[page-in_260ms_cubic-bezier(0.16,1,0.3,1)_both]">
          <Outlet />
        </div>
      </main>
    </div>
  )
}