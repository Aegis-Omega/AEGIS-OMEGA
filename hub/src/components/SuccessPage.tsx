// Post-payment landing for the /success route.
// Display-only: payment capture and API-key provisioning happen server-side in
// supabase/functions/verify-paypal. This page never mints or holds a key — it
// confirms the order and points the buyer to where their key was delivered.
import { useEffect, useState } from 'react'

export function SuccessPage() {
  const [orderId, setOrderId] = useState<string | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    // PayPal redirect flows pass token/PayerID; our inline flow passes order.
    setOrderId(params.get('order') ?? params.get('token'))
  }, [])

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col items-center px-4 py-16">
      <a
        href="/"
        className="flex items-center gap-2 mb-12 text-gray-400 hover:text-white transition-colors text-sm"
      >
        ← aegisomega.com
      </a>

      <div className="max-w-xl mx-auto p-8 rounded-lg border border-indigo-500/40 bg-indigo-950/30 text-center">
        <div className="flex items-center justify-center gap-2 mb-5">
          <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <span className="text-green-400 text-sm font-mono">PAYMENT CONFIRMED</span>
        </div>

        <h1 className="text-2xl font-bold text-white mb-3">Thank you — your access is provisioned</h1>

        <p className="text-gray-400 text-sm leading-relaxed mb-4">
          Your API key was provisioned the moment payment cleared and sent to the email
          you entered at checkout. Store it securely — it is shown only once. Pass it as
          the <code className="text-indigo-300 text-xs">x-api-key</code> header on every request.
        </p>

        {orderId && (
          <p className="text-gray-500 text-xs font-mono mb-4">
            Order reference: <span className="text-gray-400">{orderId}</span>
          </p>
        )}

        <p className="text-gray-500 text-xs leading-relaxed">
          Endpoint:{' '}
          <code className="text-gray-400">https://aegis-vertex.aegisomega.com/platform/collaborate</code>
        </p>
      </div>

      <p className="text-gray-600 text-xs mt-8 text-center max-w-md leading-relaxed">
        Didn&apos;t get your key? Check spam, then reach out at{' '}
        <a href="mailto:info@aegisomega.com" className="text-gray-500 hover:text-gray-400 underline">
          info@aegisomega.com
        </a>{' '}
        with your order reference. You can also revisit{' '}
        <a href="/pricing" className="text-indigo-400 hover:text-indigo-300 underline">
          the pricing page
        </a>.
      </p>
    </div>
  )
}
