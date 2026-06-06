// AEGIS-Ω — hub router
// /          → HomepageLanding (enterprise B2B)
// /runtime   → AegisRuntime (live constitutional substrate demo)
// /success   → SuccessPage
import { SuccessPage } from './components/SuccessPage.js'
import { HomepageLanding } from './components/HomepageLanding.js'
import { AegisRuntime } from './components/AegisRuntime.js'

export default function App() {
  const path = window.location.pathname
  if (path === '/success') return <SuccessPage />
  if (path === '/runtime') return <AegisRuntime />
  return <HomepageLanding />
}
