// AEGIS-Ω hub router
// /               → HomepageLanding (product landing page)
// /platform       → PlatformPage (agent catalog · execution trace · use cases)
// /docs           → DocsPage (API reference)
// /pricing        → PricingPage (API key purchase via Stripe)
// /claim-sponsor  → ClaimSponsorPage (GitHub Sponsors key claim)
// /runtime        → AegisRuntime (constitutional consciousness showcase)
import { AegisRuntime }      from './components/AegisRuntime.js'
import { ClaimSponsorPage }  from './components/ClaimSponsorPage.js'
import { DocsPage }          from './components/DocsPage.js'
import { HomepageLanding }   from './components/HomepageLanding.js'
import { PlatformPage }      from './components/PlatformPage.js'
import { PricingPage }       from './components/PricingPage.js'

const path = window.location.pathname

export default function App() {
  if (path === '/pricing')        return <PricingPage />
  if (path === '/claim-sponsor')  return <ClaimSponsorPage />
  if (path === '/docs')           return <DocsPage />
  if (path === '/platform')       return <PlatformPage />
  if (path === '/runtime')        return <AegisRuntime />
  return <HomepageLanding />
}
