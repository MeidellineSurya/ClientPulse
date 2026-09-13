import { AlertTriangle, LayoutGrid, LogOut, Settings as SettingsIcon } from "lucide-react"
import { NavLink, Outlet } from "react-router-dom"

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Button } from "@/components/ui/button"
import { TooltipProvider } from "@/components/ui/tooltip"
import { useAuth } from "@/components/auth/auth-context"

const NAV_ITEMS = [
  { to: "/", label: "Portfolio", icon: LayoutGrid, end: true },
  { to: "/alerts", label: "Alerts", icon: AlertTriangle, end: false },
  { to: "/settings", label: "Settings", icon: SettingsIcon, end: false },
]

export function AppLayout() {
  const { email, signOut } = useAuth()

  return (
    <TooltipProvider>
      <SidebarProvider>
        <Sidebar collapsible="icon">
          <SidebarHeader className="px-3 py-4">
            <span className="text-lg font-semibold tracking-tight group-data-[collapsible=icon]:hidden">
              ClientPulse
            </span>
          </SidebarHeader>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupContent>
                <SidebarMenu>
                  {NAV_ITEMS.map((item) => (
                    <SidebarMenuItem key={item.to}>
                      <SidebarMenuButton asChild tooltip={item.label}>
                        <NavLink
                          to={item.to}
                          end={item.end}
                          className={({ isActive }) =>
                            isActive ? "font-medium text-sidebar-accent-foreground" : ""
                          }
                        >
                          <item.icon />
                          <span>{item.label}</span>
                        </NavLink>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
        <SidebarInset>
          <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
            <SidebarTrigger />
            <span className="ml-auto hidden text-sm text-muted-foreground sm:inline">
              {email}
            </span>
            <Button
              aria-label="Sign out"
              size="sm"
              variant="ghost"
              onClick={() => void signOut()}
            >
              <LogOut />
              <span className="hidden sm:inline">Sign out</span>
            </Button>
          </header>
          <main className="flex-1 overflow-auto p-6">
            <Outlet />
          </main>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  )
}
