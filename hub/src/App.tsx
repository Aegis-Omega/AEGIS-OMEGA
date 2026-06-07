// AEGIS-Ω hub router
// /          → HomepageLanding (product landing page)
// /runtime   → AegisRuntime (living consciousness automaton, linked from landing CTA)
// /pricing   → PricingPage (API key purchase)
import { AegisRuntime }     from './components/AegisRuntime.js'
import { HomepageLanding }  from './components/HomepageLanding.js'
import { PricingPage }      from './components/PricingPage.js'

const path = window.location.pathname

export default function App() {
  if (path === '/pricing') return <PricingPage />
  if (path === '/runtime') return <AegisRuntime />
  return <HomepageLanding />
}
