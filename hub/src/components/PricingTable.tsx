import { Zap } from 'lucide-react'

function captureEvent(event: string, props?: Record<string, unknown>): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ph = (window as any).posthog
  if (typeof ph?.capture === 'function') ph.capture(event, props)
}

// Lemon Squeezy checkout links (works globally including Bosnia/Balkans).
// Set VITE_LS_LINK_SINGLE / _STARTER / _FULL in Vercel env vars.
//
// Setup (5 min):
//   1. Create account at app.lemonsqueezy.com
//   2. Create a store → add 3 products ($19 / $29 / $39)
//   3. All 3 products use the SAME redirect URL (order_id is injected by LS):
//        https://aegisomega.com/success?order_id={order_id}
//   4. Copy each product's checkout URL and set it as the env var below.
//
// Lemon Squeezy is a Merchant of Record — they handle VAT/tax globally.
// No Stripe account needed. Works in 100+ countries.
const LS_LINKS = {
  single:  import.meta.env.VITE_LS_LINK_SINGLE  ?? '#pricing',
  starter: import.meta.env.VITE_LS_LINK_STARTER ?? '#pricing',
  full:    import.meta.env.VITE_LS_LINK_FULL    ?? '#pricing',
}

interface Tier {
  id: 'single' | 'starter' | 'full'
  name: string
  price: number
  originalPrice?: number
  desc: string
  items: string[]
  highlight: boolean
  badge?: string
}

const TIERS: Tier[] = [
  {
    id: 'single',
    name: 'Single Tool',
    price: 19,
    desc: 'Pick any one — Platform Picker, Hook Generator, or Content Calendar.',
    items: [
      '1 AI tool of your choice',
      'Unlimited runs (your API key)',
      'Instant access — no keys, no email',
      'No subscriptions, ever',
      'Full source code',
    ],
    highlight: false,
  },
  {
    id: 'starter',
    name: 'Starter Pack',
    price: 29,
    originalPrice: 38,
    desc: 'Any two tools at a discount. Mix and match what you need.',
    items: [
      '2 AI tools of your choice',
      'Save $9 vs buying separate',
      'Unlimited runs (your API key)',
      'Instant access — no keys, no email',
      'No subscriptions, ever',
      'Full source code',
    ],
    highlight: true,
    badge: 'Most popular',
  },
  {
    id: 'full',
    name: 'Full Toolkit',
    price: 39,
    originalPrice: 57,
    desc: 'All three tools — the complete creator AI arsenal.',
    items: [
      'All 3 AI tools',
      'Save $18 vs buying separate',
      'Unlimited runs (your API key)',
      'Instant access — no keys, no email',
      'No subscriptions, ever',
      'Full source code',
      'Future tool updates included',
    ],
    highlight: false,
    badge: 'Best value',
  },
]

export function PricingTable() {
  return (
    <div className="grid md:grid-cols-3 gap-4">
      {TIERS.map(tier => (
        <div
          key={tier.id}
          className={`rounded-2xl p-6 border flex flex-col gap-4 ${
            tier.highlight
              ? 'border-hub-accent/50 bg-hub-accent/5 shadow-lg shadow-hub-accent/10'
              : 'border-hub-border bg-hub-surface'
          }`}
        >
          {tier.badge && (
            <span className="text-xs font-semibold text-hub-glow bg-hub-accent/10 border border-hub-accent/30 rounded-full px-3 py-0.5 w-fit">
              {tier.badge}
            </span>
          )}
          <div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-hub-text">${tier.price}</span>
              {tier.originalPrice && (
                <span className="text-hub-muted text-sm line-through">${tier.originalPrice}</span>
              )}
            </div>
            <div className="font-semibold text-hub-text mt-0.5">{tier.name}</div>
            <p className="text-hub-muted text-sm mt-1">{tier.desc}</p>
          </div>
          <ul className="space-y-1.5 flex-1">
            {tier.items.map(item => (
              <li key={item} className="flex items-center gap-2 text-sm text-hub-muted">
                <span className="text-hub-glow">✓</span>
                {item}
              </li>
            ))}
          </ul>
          <a
            href={LS_LINKS[tier.id]}
            onClick={() => captureEvent('checkout_click', { plan: tier.id, price: tier.price })}
            className={`flex items-center justify-center gap-2 text-sm font-semibold py-3 rounded-xl transition-all ${
              tier.highlight
                ? 'bg-hub-accent text-white hover:opacity-90'
                : 'border border-hub-accent/50 text-hub-glow hover:bg-hub-accent/10'
            }`}
          >
            <Zap size={14} />
            Get {tier.name} — ${tier.price}
          </a>
        </div>
      ))}
    </div>
  )
}
