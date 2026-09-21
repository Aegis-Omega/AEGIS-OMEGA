import { useEffect, useRef, useState } from 'react'

const SUPABASE_URL = (import.meta.env.VITE_SUPABASE_URL as string | undefined)
  || 'https://rwehltdwpsncnwxzkwik.supabase.co'
const PAYPAL_CLIENT_ID = (import.meta.env.VITE_PAYPAL_CLIENT_ID as string | undefined) ?? ''
const CAPTURE_URL = `${SUPABASE_URL}/functions/v1/verify-paypal`
const AUDIT_PRICE = '3000.00'

export function AuditCheckoutPage() {
  const [email, setEmail] = useState('')
  const [ready, setReady] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [paidOrder, setPaidOrder] = useState<string | null>(null)
  const buttonRef = useRef<HTMLDivElement | null>(null)
  const emailRef = useRef(email)

  useEffect(() => { emailRef.current = email }, [email])

  useEffect(() => {
    if (!PAYPAL_CLIENT_ID) return
    if ((window as any).paypal) { setReady(true); return }
    const script = document.createElement('script')
    script.src = `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(PAYPAL_CLIENT_ID)}&currency=USD&intent=capture`
    script.onload = () => setReady(true)
    script.onerror = () => setError('Could not load PayPal. Contact api@aegisomega.com')
    document.body.appendChild(script)
  }, [])

  useEffect(() => {
    if (!ready || !buttonRef.current || paidOrder) return
    const paypal = (window as any).paypal
    if (!paypal) return
    const container = buttonRef.current
    container.innerHTML = ''

    const buttons = paypal.Buttons({
      style: { layout: 'vertical', color: 'gold', shape: 'pill', label: 'pay' },
      onClick: (_data: unknown, actions: any) => {
        const em = emailRef.current.trim()
        if (!em || !em.includes('@')) {
          setError('Enter a valid business email first.')
          return actions.reject()
        }
        setError(null)
        return actions.resolve()
      },
      createOrder: (_data: unknown, actions: any) => actions.order.create({
        intent: 'CAPTURE',
        purchase_units: [{
          amount: { value: AUDIT_PRICE, currency_code: 'USD' },
          description: 'AEGIS Agent Action Boundary Audit — founder pilot',
        }],
      }),
      onApprove: async (data: { orderID: string }) => {
        setLoading(true); setError(null)
        try {
          const response = await fetch(CAPTURE_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              order_id: data.orderID,
              tier: 'audit',
              email: emailRef.current.trim(),
            }),
          })
          const result = await response.json() as { paid?: boolean; order_id?: string; error?: string }
          if (!response.ok || !result.paid) throw new Error(result.error ?? `HTTP ${response.status}`)
          setPaidOrder(result.order_id ?? data.orderID)
        } catch (e) {
          setError(String(e))
        } finally {
          setLoading(false)
        }
      },
      onError: (e: unknown) => setError(`PayPal error: ${String(e)}`),
    })

    buttons.render(container).catch(() => {})
    return () => { try { buttons.close() } catch { /* noop */ } }
  }, [ready, paidOrder])

  if (paidOrder) {
    return (
      <main style={{ minHeight: '100vh', background: '#06070C', color: '#F7F7FB', padding: '96px 24px', fontFamily: 'Inter, sans-serif' }}>
        <div style={{ maxWidth: 720, margin: '0 auto' }}>
          <div style={{ fontFamily: 'monospace', color: '#34D399', marginBottom: 16 }}>PAYMENT RECEIVED</div>
          <h1 style={{ fontSize: 44, marginBottom: 20 }}>Agent Action Boundary Audit</h1>
          <p style={{ color: '#C9CBD6', lineHeight: 1.7 }}>
            Your $3,000 founder-pilot payment was captured. We will confirm the representative
            tool-using workflow and kickoff scope before work begins.
          </p>
          <p style={{ color: '#8B8E9C', fontFamily: 'monospace' }}>PayPal order: {paidOrder}</p>
          <a href="mailto:api@aegisomega.com?subject=AEGIS%20Audit%20Kickoff" style={{ color: '#C8A96E' }}>
            Send kickoff details →
          </a>
        </div>
      </main>
    )
  }

  return (
    <main style={{ minHeight: '100vh', background: '#06070C', color: '#F7F7FB', padding: '80px 24px', fontFamily: 'Inter, sans-serif' }}>
      <div style={{ maxWidth: 760, margin: '0 auto' }}>
        <a href="/" style={{ color: '#8B8E9C', textDecoration: 'none' }}>← AEGIS-Ω</a>
        <div style={{ fontFamily: 'monospace', color: '#C8A96E', marginTop: 48, marginBottom: 16 }}>FOUNDER PILOT · FIXED FEE</div>
        <h1 style={{ fontSize: 'clamp(38px,7vw,72px)', lineHeight: 1, letterSpacing: '-0.04em', margin: '0 0 24px' }}>
          Agent Action Boundary Audit
        </h1>
        <p style={{ fontSize: 20, color: '#C9CBD6', lineHeight: 1.6 }}>
          One tool-using workflow. Authority surface map, pre-mutation control review,
          fail-open / fail-closed findings, receiptability and lineage assessment, and prioritized remediation.
        </p>

        <div style={{ margin: '36px 0', padding: 24, border: '1px solid rgba(255,255,255,.12)', borderRadius: 16, background: 'rgba(255,255,255,.03)' }}>
          <div style={{ fontSize: 36, fontWeight: 800 }}>$3,000 <span style={{ fontSize: 14, color: '#8B8E9C', fontWeight: 400 }}>USD · one-time</span></div>
          <ul style={{ color: '#C9CBD6', lineHeight: 1.9 }}>
            <li>One agentic / tool-using workflow</li>
            <li>Technical findings brief + engineering evidence appendix</li>
            <li>Representative workflow or staging path is sufficient</li>
            <li>Manual scope confirmation before kickoff</li>
          </ul>
        </div>

        <label style={{ display: 'block', fontFamily: 'monospace', fontSize: 12, color: '#8B8E9C', marginBottom: 8 }}>BUSINESS EMAIL</label>
        <input
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          placeholder="you@company.com"
          style={{ width: '100%', boxSizing: 'border-box', background: 'rgba(255,255,255,.04)', color: '#fff', border: '1px solid rgba(255,255,255,.14)', borderRadius: 10, padding: '14px 16px', fontSize: 16, marginBottom: 18 }}
        />

        {error && <div style={{ color: '#F87171', marginBottom: 14 }}>{error}</div>}
        {!PAYPAL_CLIENT_ID && <div style={{ color: '#F87171', marginBottom: 14 }}>PayPal client ID is not configured.</div>}
        <div ref={buttonRef} style={{ minHeight: 52, opacity: loading ? .6 : 1 }} />
        <p style={{ color: '#6B7280', fontSize: 12, lineHeight: 1.6, marginTop: 18 }}>
          This purchase is a fixed-fee technical audit engagement. It is not a formal compliance certification
          and does not imply platform-wide safety guarantees.
        </p>
      </div>
    </main>
  )
}
