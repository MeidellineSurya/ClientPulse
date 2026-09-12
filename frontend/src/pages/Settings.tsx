import { Calendar, FileSpreadsheet, Mail } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

const CONNECTIONS = [
  {
    icon: Mail,
    title: "Gmail",
    description: "Pulls response-time and thread-count signals from metadata only — message bodies are never read.",
  },
  {
    icon: Calendar,
    title: "Google Calendar",
    description: "Pulls meeting frequency and cancellation signals from the connected calendar.",
  },
  {
    icon: FileSpreadsheet,
    title: "CSV Upload",
    description: "Upload invoice/payment history to compute the payment-lag signal.",
  },
]

export function Settings() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">Connect the data sources ClientPulse uses to compute signals.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {CONNECTIONS.map((connection) => (
          <Card key={connection.title}>
            <CardHeader>
              <connection.icon className="size-6 text-muted-foreground" />
              <CardTitle className="pt-2">{connection.title}</CardTitle>
              <CardDescription>{connection.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <Button variant="outline" className="w-full" disabled>
                Connect (not wired up yet)
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
