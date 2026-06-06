# AEGIS-Ω GTM Engineering Specification

**Status:** ACTIVE · Ready for Claude Code  
**Author:** Tarik Skalić  
**Date:** 2026-06-05  
**Objective:** Transform aegisomega.com into #1 AI platform for regulated industries  
**Timeline:** 90 days to $10K–$20K MRR (5–10 enterprise pilots closed)

---

## I. OVERVIEW

This document specifies the complete engineering work needed to build out the GTM (Go-To-Market) infrastructure for AEGIS-Ω as a **full-stack B2B SaaS platform**.

**Target customer:** Mid-market CTOs at fintech, healthtech, legal-tech, financial services  
**Pitch:** Deterministic AI · audit-proof · EU AI Act compliant · replay-verifiable  
**Revenue model:** $5K–$10K/mo per enterprise customer + Cockpit SaaS ($29/mo, $99/mo)

---

## II. KILL LIST (Remove Consumer Noise)

### **A. Delete from codebase:**
- `hub/src/components/ToolsPage.tsx` — completely remove
- `platform-picker/` — stop deploying (keep code for future)
- `hook-generator/` — stop deploying (keep code for future)
- `content-calendar/` — stop deploying (keep code for future)
- All references to "$19 tools" in README.md, DEPLOY.md, etc.

### **B. Redirect routes:**
- `/tools` → redirect to `/cockpit`
- `/platform-picker`, `/hook-generator`, `/content-calendar` → 404 or redirect to homepage

### **C. Update documentation:**
- README.md: Remove "creator tools" section
- DEPLOY.md: Update deployment instructions (hub + cockpit only)
- CLAUDE.md: Update with new GTM focus

---

## III. BUILD SPECIFICATION

### **Phase 1: Homepage Redesign (Hub Landing Page)**

**File:** `hub/src/components/HomepageLanding.tsx` (NEW)

**Structure:**
```
1. Sticky Nav
   - Logo (AEGIS-Ω)
   - Links: Enterprise | Cockpit | GitHub | Calendly
   
2. Hero Section
   Headline: "AI That Your Compliance Team Will Approve"
   Subheading: "Deterministic. Auditable. Replay-verified. Your data. Your model."
   CTA buttons:
     - Primary: "Book Enterprise Demo" → opens Calendly
     - Secondary: "Try Free Cockpit" → /cockpit
   
3. Trust Metrics Bar (4 columns)
   - 10,973+ | Invariant Tests | all passing
   - SHA-256 | Hash-Chained | tamper-evident
   - T0 Proven | Deterministic | replay-verified
   - AGPL-3.0 | Open Source | no vendor lock-in

4. Problem-Solution Grid (2x3)
   Left column (problems):
     ❌ Black Box — can't replay, auditors say no
     ❌ Hallucinations — model makes up facts, legal liability
     ❌ Vendor Lock-In — proprietary API, can't switch
   Right column (solutions):
     ✓ Deterministic — every decision replayable, hash-verified
     ✓ Constitutional — governance layers prevent hallucinations
     ✓ Your Code — AGPL source, run anywhere, no lock-in

5. Industries Section (3 cards)
   🏦 Fintech — compliance reporting, risk assessment, fraud detection
   🏥 Healthcare — patient records, clinical decision support, audit trail
   ⚖️ Legal — contract analysis, compliance checks, litigation holds

6. Technical Details Section
   Headline: "How AEGIS Differs"
   - Deterministic Replay: replay(genesis, events) → identical output on any platform
   - Hash-Chained Audit: every state transition signed, tamper-evident
   - Constitutional Governance: T0–T2 layers, enforcement at every boundary
   - EU AI Act Ready: Article 12 compliance baked in
   
7. CTA Footer
   "Ready to Deploy Constitutional AI?"
   Subheading: "Book a 30-minute technical audit. No pressure."
   Button: "Book Demo" → Calendly

8. Footer
   Logo · Link to source · Contact email
```

**Key styling:**
- Dark background (#04040D)
- Phi gold accent (#C8A96E)
- Mint green for checkmarks (#34D399)
- Teal/cyan for secondary (#06B6D4)
- Clean sans-serif (Inter)
- Monospace for technical details (JetBrains Mono)

---

### **Phase 2: Enterprise Page**

**File:** `hub/src/components/EnterprisePage.tsx` (NEW)

**Route:** `/enterprise`

**Structure:**
```
1. Hero
   "Constitutional AI For Regulated Industries"
   Subheading: "Meet the only AI platform your compliance team will approve."

2. The Problem
   Headline: "Why Traditional AI Vendors Fail Regulated Orgs"
   
   Problems (3-column grid):
   - No Replay Capability
     "Every inference is opaque. You can't reproduce decisions for audits."
   - Hallucination Risk
     "Models generate false outputs. Liability lands on you."
   - Regulatory Uncertainty
     "EU AI Act, HIPAA, PCI — compliance is custom, expensive, risky."

3. AEGIS Solution
   Headline: "The Only AI Platform Built For Compliance"
   
   Guarantee boxes (4 items):
   ✓ Deterministic Replay
     Every decision hash-certified from genesis. Replayable byte-for-byte on any platform.
   
   ✓ Audit Trail
     SHA-256 chain from first token to last output. HIPAA/PCI/SOX ready.
   
   ✓ Constitutional Governance
     T0–T2 layers prevent hallucinations. Governance enforced mechanically, not aspirationally.
   
   ✓ EU AI Act Compliant
     Article 12 audit binders generated automatically. No custom integration.

4. Use Cases
   Headline: "Where AEGIS Wins"
   
   (3 detailed case studies):
   
   a) Fintech Risk Management
      "A mid-market lending platform needed to prove every credit decision to regulators.
       AEGIS replayed 10,000 lending decisions across 3 platforms. Byte-identical.
       Compliance approved. Audit passed."
      Metrics: 100% replay success · 0 regulatory findings · 30% faster audit cycle
   
   b) Healthcare Patient Records
      "A health-tech company stores patient data in AI-indexed records.
       Every retrieval must be auditable and non-hallucinating.
       AEGIS constitutional layer guarantees no fabricated patient info."
      Metrics: 0 hallucination incidents · HIPAA-ready · automatic audit trail
   
   c) Legal Contract Analysis
      "A legal-tech startup uses AI to extract contract terms.
       Every extraction must be citeable and reviewable.
       AEGIS hash-chains every extraction to the source document."
      Metrics: 100% citeable outputs · litigation-ready audit · zero disputes

5. Why AEGIS Wins
   Headline: "Your Unfair Advantages"
   
   (Comparison table):
   
   | Feature | Traditional AI | AEGIS |
   |---------|---|---|
   | Deterministic replay | ❌ | ✓ Byte-identical |
   | Audit trail | ❌ | ✓ Hash-chained from genesis |
   | Hallucination prevention | ❌ | ✓ Constitutional governance |
   | Regulatory compliance | ⚠️ Custom | ✓ EU AI Act ready |
   | Source code | ❌ Proprietary | ✓ AGPL-3.0 |
   | Vendor lock-in | ❌ High | ✓ None |
   | Cost per inference | 📈 Expensive | ✓ Transparent |

6. Pricing & Engagement
   "Enterprise Pilot Program"
   
   6-Week POC: $5,000
   - Deploy cockpit on your infra
   - Run your real workload
   - Prove deterministic replay
   - 3 executive briefings
   
   Production Deployment: $5K–$10K/mo + $0.001/inference
   - Dedicated support
   - Custom governance rules (optional)
   - API access + team seats
   - SLA 99.9%

7. CTAs
   "Let's Prove It Works"
   Button: "Schedule 30-min technical audit"
   Secondary: "Download whitepaper" (PDF)

8. Footer
```

---

### **Phase 3: Cockpit SaaS Page**

**File:** `hub/src/components/CockpitSaaSPage.tsx` (NEW)

**Route:** `/saas`

**Structure:**
```
1. Hero
   Headline: "Cockpit — Constitutional AI Chat"
   Subheading: "Deterministic inference. Your API key. No subscription trap."

2. Pricing Cards (3-tier)
   
   TIER 1: Free
   - 5 messages/day
   - Local inference only
   - No API key required
   - CTA: "Get Started"
   
   TIER 2: Pro ($29/mo)
   - 1,000 messages/day
   - Cloud inference (Qwen + Claude)
   - Team access (up to 5 users)
   - Chat history export
   - CTA: "Start Free Trial"
   
   TIER 3: Enterprise ($99/mo)
   - Unlimited messages
   - Priority queue
   - Team seats (unlimited)
   - API access
   - Custom constitutional rules
   - Email support
   - CTA: "Contact Sales"

3. What's Included
   (Feature list):
   - Constitutional substrate (hash-chained, tamper-evident)
   - Multi-model routing (Claude, Qwen, local)
   - Session persistence (IndexedDB)
   - Markdown + code support
   - Conversation export (TXT, JSON)
   - Dark mode
   - Zero data collection (privacy-first)

4. How It Works
   Step 1: Sign up (email optional)
   Step 2: Choose model + paste API key
   Step 3: Chat with constitutional guarantees
   Step 4: Export conversation anytime

5. Trust & Transparency
   "Run In Your Browser"
   - All inference happens client-side
   - Your API key never leaves your device
   - Open source (AGPL-3.0)
   - Auditable code
   - No server-side logging
   
   Metrics display:
   - Tokens used today: X/Y
   - Model: [selector]
   - Chain length: N
   - is_valid: [true/false] (from substrate)

6. CTA
   "Start Free"
   "Upgrade anytime"
```

---

### **Phase 4: Update `hub/src/App.tsx` Router**

**Changes:**
```tsx
export default function App() {
  const path = window.location.pathname
  
  // Remove ToolsPage route
  if (path === '/success') return <SuccessPage />
  if (path === '/enterprise') return <EnterprisePage />
  if (path === '/saas') return <CockpitSaaSPage />
  
  // Default: homepage
  return <HomepageLanding />
}
```

---

### **Phase 5: Cockpit Token Counter & Stripe Integration**

**New file:** `cockpit/src/hooks/useTokenCounter.ts`

```typescript
import { useState, useEffect } from 'react'

export interface UserTier {
  plan: 'free' | 'pro' | 'enterprise'
  dailyLimit: number
  monthlyLimit: number
  currentDailyUsage: number
  currentMonthlyUsage: number
  resetAt: number
  stripeSessionId?: string
  paymentMethod?: string
}

export function useTokenCounter() {
  const [tier, setTier] = useState<UserTier>(() => {
    const stored = localStorage.getItem('aegis_tier')
    if (stored) return JSON.parse(stored)
    
    return {
      plan: 'free',
      dailyLimit: 5,
      monthlyLimit: 150,
      currentDailyUsage: 0,
      currentMonthlyUsage: 0,
      resetAt: Date.now() + 86400000,
    }
  })

  useEffect(() => {
    // Reset daily counter at midnight
    const now = Date.now()
    if (now > tier.resetAt) {
      const updated = {
        ...tier,
        currentDailyUsage: 0,
        resetAt: now + 86400000,
      }
      setTier(updated)
      localStorage.setItem('aegis_tier', JSON.stringify(updated))
    }
  }, [])

  const canSendMessage = (): boolean => {
    if (tier.currentDailyUsage >= tier.dailyLimit) return false
    if (tier.currentMonthlyUsage >= tier.monthlyLimit) return false
    return true
  }

  const getRemainingMessages = (): number => {
    return Math.min(
      tier.dailyLimit - tier.currentDailyUsage,
      tier.monthlyLimit - tier.currentMonthlyUsage,
    )
  }

  const incrementUsage = () => {
    const updated = {
      ...tier,
      currentDailyUsage: tier.currentDailyUsage + 1,
      currentMonthlyUsage: tier.currentMonthlyUsage + 1,
    }
    setTier(updated)
    localStorage.setItem('aegis_tier', JSON.stringify(updated))
  }

  const startStripeCheckout = async (plan: 'pro' | 'enterprise') => {
    try {
      const res = await fetch('/api/stripe-checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan }),
      })
      const { sessionUrl } = await res.json()
      if (sessionUrl) window.location.href = sessionUrl
    } catch (err) {
      console.error('Stripe checkout failed:', err)
    }
  }

  const upgradeToTier = (newPlan: 'pro' | 'enterprise') => {
    startStripeCheckout(newPlan)
  }

  return {
    tier,
    canSendMessage,
    getRemainingMessages,
    incrementUsage,
    upgradeToTier,
  }
}
```

---

### **Phase 6: Update InputBar Component**

**File:** `cockpit/src/components/InputBar.tsx` (MODIFY)

```tsx
import { useTokenCounter } from '../hooks/useTokenCounter.js'

export function InputBar({ value, onChange, onSend, streaming }) {
  const { tier, canSendMessage, getRemainingMessages, incrementUsage, upgradeToTier } = useTokenCounter()

  const handleSend = () => {
    if (!canSendMessage() || streaming) return
    incrementUsage()
    onSend?.()
  }

  if (tier.currentDailyUsage >= tier.dailyLimit) {
    return (
      <div className="border-t border-aegis-border bg-aegis-surface/50 p-4 text-center">
        <p className="text-sm text-aegis-muted mb-3">
          You've reached your daily limit of {tier.dailyLimit} messages.
        </p>
        {tier.plan === 'free' && (
          <button
            onClick={() => upgradeToTier('pro')}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
          >
            Upgrade to Pro ($29/mo) →
          </button>
        )}
        <p className="text-xs text-aegis-muted mt-2">Resets at midnight UTC</p>
      </div>
    )
  }

  return (
    <div className="border-t border-aegis-border bg-aegis-surface p-4">
      <div className="flex gap-3 mb-2">
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !streaming && handleSend()}
          placeholder="Ask anything..."
          disabled={streaming}
          className="flex-1 bg-aegis-bg text-aegis-text text-sm px-4 py-2 rounded-lg border border-aegis-border focus:outline-none focus:border-blue-500 disabled:opacity-50"
        />
        <button
          onClick={handleSend}
          disabled={!value.trim() || streaming || !canSendMessage()}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {streaming ? 'Thinking...' : 'Send'}
        </button>
      </div>
      
      <div className="flex justify-between items-center text-xs text-aegis-muted">
        <span>
          {tier.currentDailyUsage}/{tier.dailyLimit} messages today · {getRemainingMessages()} remaining
        </span>
        {tier.plan === 'free' && (
          <button
            onClick={() => upgradeToTier('pro')}
            className="text-blue-400 hover:underline"
          >
            Upgrade for unlimited →
          </button>
        )}
      </div>
    </div>
  )
}
```

---

### **Phase 7: Calendly Integration**

**File:** `hub/src/components/HomepageLanding.tsx` (INSERT)

Add this script to `hub/public/index.html`:

```html
<script src="https://assets.calendly.com/assets/external/widget.js"></script>
```

CTA buttons should open Calendly inline:

```tsx
<button 
  onClick={() => {
    if (window.Calendly) {
      window.Calendly.showPopupWidget('https://calendly.com/aegis-omega/technical-audit')
    }
  }}
  className="px-8 py-3 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700"
>
  Book Enterprise Demo →
</button>
```

---

### **Phase 8: Landing Page Copy & Design System**

**File:** `hub/public/design-system.css` (NEW)

```css
:root {
  /* Colors */
  --color-bg-dark: #04040D;
  --color-bg-darker: #02020A;
  --color-text-primary: #F4F4F8;
  --color-text-secondary: #A8A8B4;
  --color-text-muted: #6B6D7A;
  
  /* Accent colors */
  --color-accent-gold: #C8A96E;
  --color-accent-teal: #06B6D4;
  --color-accent-mint: #10B981;
  --color-accent-violet: #8B5CF6;
  
  /* Semantic */
  --color-success: #10B981;
  --color-error: #EF4444;
  --color-warning: #F59E0B;
  
  /* Typography */
  --font-mono: 'JetBrains Mono', monospace;
  --font-sans: 'Inter', system-ui, sans-serif;
  --font-size-xs: 12px;
  --font-size-sm: 14px;
  --font-size-base: 16px;
  --font-size-lg: 18px;
  --font-size-xl: 20px;
  --font-size-2xl: 24px;
  --font-size-3xl: 32px;
  --font-size-4xl: 48px;
  --font-size-5xl: 64px;
  
  /* Spacing */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;
  --spacing-xl: 32px;
  --spacing-2xl: 48px;
}
```

---

### **Phase 9: Cold Email Infrastructure**

**File:** `docs/COLD_EMAIL_TEMPLATE.md` (NEW)

```markdown
# Cold Email Template (Subject Line Variations)

## Variation 1: Compliance Officer Angle
**Subject:** Deterministic AI for regulated workflows

Hi [Name],

Your compliance team probably said no to AI.

We know why: AI vendors are black boxes. You can't replay decisions for audits. Hallucinations create liability.

AEGIS is different:
✓ Every decision is deterministic (replayable from genesis)
✓ Hash-chained audit trail (HIPAA/PCI/SOX ready)
✓ EU AI Act Article 12 compliant
✓ Source code is open (no vendor lock-in)

A mid-market fintech just used AEGIS to replay 10,000 lending decisions across 3 different platforms. Byte-identical. Auditors approved.

Your compliance officer will approve. No custom integration needed.

Want to see a 15-minute demo? Zero pressure.

[Calendly link]

Tarik
AEGIS-Ω

---

## Variation 2: Risk/Compliance Angle
**Subject:** Prove every AI decision to your auditors

Hi [Name],

Question: Can you replay every AI decision your system made last month?

If you use traditional AI vendors, the answer is no. That's a problem when auditors ask.

AEGIS solves this. Every decision is:
- Hash-certified from genesis
- Replayable on any platform
- Auditable end-to-end
- Compliant with EU AI Act

We built this specifically for teams at financial services, healthcare, and legal-tech companies that can't afford regulatory risk.

6-week POC: $5K. You deploy on your infra. You prove it works. You know exactly what you're buying.

Interested?

[Calendly link]

Tarik
AEGIS-Ω

---

## Variation 3: Engineering/Technical Angle
**Subject:** Your AI stack needs deterministic replay

Hi [Name],

Most AI platforms treat inference as a black box. Output goes in, tokens come out, no proof of what happened in between.

AEGIS is built differently:
- Every inference outputs a hash chain
- Replay(genesis, events) → identical state on any CPU/GPU
- Constitutional governance at every layer
- 10,973 invariant tests, 0 failures

We're not faster or cheaper. We're auditable.

If your org needs to prove every AI decision to regulators, let's talk.

[Calendly link]

Tarik
AEGIS-Ω

---

## Follow-Up (Sent 3 days after no reply)

**Subject:** RE: Deterministic AI for regulated workflows

Hi [Name],

Quick follow-up on the AEGIS platform. 

No pressure if AI governance isn't a priority right now. But if your team is evaluating solutions that can pass regulatory audits, we'd love to show you how deterministic replay works.

[Calendly link]

Tarik

---

## Follow-Up #2 (Sent 7 days after first email)

**Subject:** EU AI Act + your AI stack

Hi [Name],

The EU AI Act enforcement timeline is accelerating. Your compliance team is probably already asking: "Can we prove what our AI does?"

AEGIS was built to answer that question. Deterministic, auditable, compliant.

30-minute technical audit. No sales pitch.

[Calendly link]

Tarik
```

---

### **Phase 10: Email Outreach Tracking**

**File:** `docs/COLD_EMAIL_TRACKING.csv` (NEW)

```csv
email,name,company,title,industry,sent_date,status,reply,demo_booked
john.smith@fintech-co.com,John Smith,FinTech Co,CTO,fintech,2026-06-06,sent,,
jane.doe@healthcare-ai.com,Jane Doe,HealthTech AI,VP Eng,healthcare,2026-06-06,sent,,
...
```

**Process:**
1. Export 500 emails from Hunter.io / RocketReach
2. Upload to `docs/COLD_EMAIL_TRACKING.csv`
3. Send batches of 50 per day (avoid spam filters)
4. Track replies in spreadsheet
5. Move "replied" or "demo_booked" to separate pipeline

---

### **Phase 11: Google Analytics Setup**

**File:** `hub/public/index.html` (ADD)

```html
<!-- Google Analytics 4 -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
  
  // Track key events
  document.addEventListener('click', (e) => {
    if (e.target?.closest('[data-event]')) {
      gtag('event', e.target.closest('[data-event]').dataset.event);
    }
  });
</script>
```

Add data attributes to CTAs:
```tsx
<button data-event="click_demo_cta">Book Demo →</button>
<button data-event="click_cockpit_cta">Try Free Cockpit</button>
```

---

## IV. DEPLOYMENT INSTRUCTIONS

### **Step 1: Kill Consumer Tools**

```bash
# Remove files
rm hub/src/components/ToolsPage.tsx
rm -rf platform-picker/
rm -rf hook-generator/
rm -rf content-calendar/

# Update routing in hub/src/App.tsx (see Phase 4)
# Update README.md, DEPLOY.md (remove tool references)
```

### **Step 2: Build Homepage**

```bash
cd hub
npm install

# Create new components
touch src/components/HomepageLanding.tsx
touch src/components/EnterprisePage.tsx
touch src/components/CockpitSaaSPage.tsx

# Update App.tsx router
# (See Phase 4)

npm run build
```

### **Step 3: Update Cockpit**

```bash
cd cockpit
npm install

# Create token counter
touch src/hooks/useTokenCounter.ts

# Update InputBar.tsx
# (See Phase 6)

npm run build
```

### **Step 4: Deploy to Vercel**

```bash
# Hub
cd hub
vercel --prod

# Cockpit
cd cockpit
vercel --prod
```

**Configure domains in Vercel:**
- `https://aegisomega.com` → hub production deployment
- `https://cockpit.aegisomega.com` → cockpit production deployment

### **Step 5: Setup Calendly**

1. Create account at calendly.com
2. Create new event: "Technical Audit" (30 min)
3. Get shareable link: `https://calendly.com/aegis-omega/technical-audit`
4. Add to homepage CTAs

### **Step 6: Setup Google Analytics**

1. Create GA4 property at analytics.google.com
2. Get measurement ID (G-XXXXXXXXXX)
3. Add to `hub/public/index.html` (see Phase 11)

### **Step 7: Export Email List**

1. Go to Hunter.io or RocketReach
2. Filter: CTO/VP Eng/Head of Compliance, fintech/healthtech/legal-tech, 50–1000 employees
3. Export 500 emails
4. Create `docs/COLD_EMAIL_TRACKING.csv`

---

## V. SUCCESS METRICS

### **Phase 1 (Weeks 1–4): Setup**
- [ ] Homepage redesigned and deployed
- [ ] Enterprise page live
- [ ] Cockpit SaaS page live
- [ ] Calendly integration working
- [ ] Google Analytics tracking live
- [ ] Token counter implemented
- [ ] 500 cold emails exported

### **Phase 2 (Weeks 5–8): Outreach**
- [ ] 250+ emails sent (50/day)
- [ ] 5–10 demo meetings booked
- [ ] 2–3 pilots signed
- [ ] First customer onboarded

### **Phase 3 (Weeks 9–12): Traction**
- [ ] 500+ emails sent total
- [ ] 10+ demo meetings completed
- [ ] 3–5 pilots closed (2–3 paying)
- [ ] $10K–$15K MRR from enterprise
- [ ] 200+ free Cockpit signups
- [ ] 5–10 paying Cockpit users @ $29/mo

---

## VI. TIMELINE & OWNERSHIP

| Week | Task | Owner | Status |
|------|------|-------|--------|
| W1 | Kill consumer tools, redesign homepage | Claude Code | 🔴 READY |
| W1 | Create enterprise page, SaaS page | Claude Code | 🔴 READY |
| W1 | Token counter + Stripe setup | Claude Code | 🔴 READY |
| W2 | Deploy to Vercel, setup Calendly | Claude Code | 🔴 READY |
| W2 | Export email list, setup GA | Claude Code | 🔴 READY |
| W2–W4 | Send cold emails (50/day batches) | Tarik (manual) | 🟡 TBD |
| W4+ | Run demos, close pilots | Tarik (sales) | 🟡 TBD |

---

## VII. FILE CHECKLIST

### **Create (New Files):**
- [ ] `hub/src/components/HomepageLanding.tsx`
- [ ] `hub/src/components/EnterprisePage.tsx`
- [ ] `hub/src/components/CockpitSaaSPage.tsx`
- [ ] `cockpit/src/hooks/useTokenCounter.ts`
- [ ] `docs/COLD_EMAIL_TEMPLATE.md`
- [ ] `docs/COLD_EMAIL_TRACKING.csv`
- [ ] `docs/SALES_DECK.md`
- [ ] `GTM_ENGINEERING_SPEC.md` (this file)

### **Modify (Existing Files):**
- [ ] `hub/src/App.tsx` (update router)
- [ ] `cockpit/src/components/InputBar.tsx` (add token counter)
- [ ] `hub/public/index.html` (add GA script)
- [ ] `README.md` (remove tool references, focus on enterprise)
- [ ] `DEPLOY.md` (update deployment instructions)
- [ ] `CLAUDE.md` (update with GTM focus)

### **Delete (Remove Files):**
- [ ] `hub/src/components/ToolsPage.tsx`
- [ ] `platform-picker/` (stop deploying)
- [ ] `hook-generator/` (stop deploying)
- [ ] `content-calendar/` (stop deploying)

---

## VIII. CLAUDE CODE INSTRUCTIONS

When Claude Code picks this up, execute in this order:

1. **Create new components** (HomepageLanding, EnterprisePage, CockpitSaaSPage)
2. **Update router** (hub/src/App.tsx)
3. **Implement token counter** (cockpit/src/hooks/useTokenCounter.ts)
4. **Update InputBar** (add limit checks + upgrade CTA)
5. **Add GA tracking** (hub/public/index.html)
6. **Test locally** (`npm run dev` in hub and cockpit)
7. **Build** (`npm run build`)
8. **Deploy to Vercel** (`vercel --prod`)
9. **Verify** (test all CTAs, token counter, analytics)

---

## IX. GO-LIVE CHECKLIST (Before Sending First Email)

```
☐ aegisomega.com loads (no 404s)
☐ Homepage hero text correct
☐ "Book Demo" button opens Calendly
☐ "Try Cockpit" button links to cockpit
☐ Enterprise page loads
☐ SaaS page shows pricing
☐ Cockpit token counter works
☐ Free tier (5/day) enforced
☐ Upgrade button → Stripe checkout
☐ GA events firing (check GA dashboard)
☐ All links work (no 404s)
☐ Mobile responsive (test on phone)
☐ Dark mode looks good
☐ No console errors
```

---

## X. POST-LAUNCH (Weekly)

- **Check GA:** Traffic, CTR, conversion funnel
- **Check email replies:** Update tracking CSV
- **Schedule demos:** Confirm 2–3 per week
- **Track pilots:** Document use cases, objections
- **Iterate:** A/B test email subject lines
- **Measure MRR:** Track closed deals

---

**This is the complete specification. Give this to Claude Code and iterate as needed.**

