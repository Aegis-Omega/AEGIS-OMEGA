// AEGIS Ω — Holon Glass unified visual shell.
// Each existing operational route retains its original component and behavior.
import { HolonHomepage, HolonNotFound, HolonRoute } from './HolonGlass.js'
import { AegisRuntime } from './components/AegisRuntime.js'
import { ClaimSponsorPage } from './components/ClaimSponsorPage.js'
import { CompliancePage } from './components/CompliancePage.js'
import { ConsolePage } from './components/console/ConsolePage.js'
import { DocsPage } from './components/DocsPage.js'
import { ResearchWorkbench } from './components/ResearchWorkbench.js'
import { PricingPage } from './components/PricingPage.js'
import { ToolsPage } from './components/ToolsPage.js'

const route = window.location.pathname.replace(/\/+$/, '') || '/'

export default function App() {
  if (route === '/') return <HolonHomepage />
  switch (route) {
    case '/pricing': return <HolonRoute route="pricing"><PricingPage /></HolonRoute>
    case '/claim-sponsor': return <HolonRoute route="claim-sponsor"><ClaimSponsorPage /></HolonRoute>
    case '/compliance': return <HolonRoute route="compliance"><CompliancePage /></HolonRoute>
    case '/docs': return <HolonRoute route="docs"><DocsPage /></HolonRoute>
    case '/platform': return <HolonRoute route="platform"><ResearchWorkbench /></HolonRoute>
    case '/console': return <HolonRoute route="console"><ConsolePage /></HolonRoute>
    case '/runtime': return <HolonRoute route="runtime"><AegisRuntime /></HolonRoute>
    case '/tools': return <HolonRoute route="tools"><ToolsPage /></HolonRoute>
    default: return <HolonNotFound />
  }
}