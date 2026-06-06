// AEGIS-Ω — hub router
// /          → AegisRuntime (living consciousness automaton)
// /tools     → ToolsPage ($19 creator tools)
// /runtime   → AegisRuntime (alias)
// /success   → SuccessPage
import { SuccessPage } from './components/SuccessPage.js'
import { AegisRuntime } from './components/AegisRuntime.js'
import { ToolsPage } from './components/ToolsPage.js'

export default function App() {
  const path = window.location.pathname
  const search = window.location.search
  if (path === '/success' || search.includes('plan=')) return <SuccessPage />
  if (path === '/tools') return <ToolsPage />
  return <AegisRuntime />
}
