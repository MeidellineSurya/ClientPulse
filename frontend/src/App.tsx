import { Navigate, Route, Routes } from "react-router-dom"

import { AppLayout } from "@/components/layout/AppLayout"
import { AccountDetail } from "@/pages/AccountDetail"
import { Accounts } from "@/pages/Accounts"
import { Alerts } from "@/pages/Alerts"
import { Connections } from "@/pages/Connections"
import { Portfolio } from "@/pages/Portfolio"

function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Portfolio />} />
        <Route path="accounts" element={<Accounts />} />
        <Route path="accounts/:id" element={<AccountDetail />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="connections" element={<Connections />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

export default App
