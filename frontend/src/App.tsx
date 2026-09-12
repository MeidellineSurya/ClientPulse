import { Route, Routes } from "react-router-dom"

import { AppLayout } from "@/components/layout/AppLayout"
import { AccountDetail } from "@/pages/AccountDetail"
import { Alerts } from "@/pages/Alerts"
import { Portfolio } from "@/pages/Portfolio"
import { Settings } from "@/pages/Settings"

function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Portfolio />} />
        <Route path="accounts/:id" element={<AccountDetail />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}

export default App
