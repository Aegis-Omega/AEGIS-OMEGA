// Pricing tiers for the three creator tools: one for $19, any two for $29,
// all three for $39. Buy once, own forever — no subscription. CTAs scroll to
// the tool list (#tools), where each card links to its live tool.
interface Tier {
  name: string
  price: number
  blurb: string
  perks: string[]
  accent: string
  featured: boolean
}

const TIERS: Tier[] = [
  {
    name: 'Single',
    price: 19,
    blurb: 'Any one tool',
    perks: ['Pick any one tool', 'Lifetime access', 'All future updates'],
    accent: '#7C3AED',
    featured: false,
  },
  {
    name: 'Duo',
    price: 29,
    blurb: 'Any two tools',
    perks: ['Pick any two tools', 'Lifetime access', 'All future updates', 'Save $9'],
    accent: '#818CF8',
    featured: true,
  },
  {
    name: 'Full Toolkit',
    price: 39,
    blurb: 'All three tools',
    perks: ['All three tools', 'Lifetime access', 'All future updates', 'Save $18'],
    accent: '#16A34A',
    featured: false,
  },
]

function capture(tier: string, price: number): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ph = (window as any).posthog
  if (typeof ph?.capture === 'function') ph.capture('pricing_cta', { tier, price })
}

export function PricingTable() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
      {TIERS.map(t => (
        <div
          key={t.name}
          className={`relative rounded-xl p-6 flex flex-col ${
            t.featured
              ? 'bg-hub-surface border-2'
              : 'bg-hub-bg border border-hub-border'
          }`}
          style={{ borderColor: t.featured ? t.accent : undefined }}
        >
          {t.featured && (
            <span
              className="absolute -top-3 left-1/2 -translate-x-1/2 text-[10px] font-semibold uppercase tracking-wider px-3 py-1 rounded-full"
              style={{ background: t.accent, color: '#0A0B0F' }}
            >
              Most popular
            </span>
          )}

          <h3 className="text-hub-text font-semibold text-sm mb-1">{t.name}</h3>
          <p className="text-hub-muted text-xs mb-4">{t.blurb}</p>

          <div className="mb-5">
            <span className="text-hub-text font-bold text-3xl">${t.price}</span>
            <span className="text-hub-muted text-xs ml-1">one-time</span>
          </div>

          <ul className="space-y-2 mb-6 flex-1">
            {t.perks.map(perk => (
              <li key={perk} className="text-hub-muted text-xs flex items-center gap-2">
                <span style={{ color: t.accent }}>✓</span>
                {perk}
              </li>
            ))}
          </ul>

          <a
            href="#tools"
            onClick={() => capture(t.name.toLowerCase(), t.price)}
            className="w-full text-center py-2.5 rounded-lg text-sm font-semibold transition-colors"
            style={{ background: t.accent + '20', color: t.accent, border: `1px solid ${t.accent}40` }}
          >
            Get {t.name} — ${t.price}
          </a>
        </div>
      ))}
    </div>
  )
}
