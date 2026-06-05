// AEGIS-Ω — constitutional AI runtime · hub router
// / → AegisRuntime (2.0 design) · /tools → ToolsPage · /success → SuccessPage
import { SuccessPage } from './components/SuccessPage.js'
import { ToolsPage } from './components/ToolsPage.js'
import { AegisRuntime } from './components/AegisRuntime.js'

export default function App() {
  const path = window.location.pathname
  if (path === '/success') return <SuccessPage />
  if (path === '/tools')   return <ToolsPage />
  return <AegisRuntime />
}
