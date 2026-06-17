// GitHub Sponsors claim page
// Sponsors visit /claim-sponsor, enter their GitHub username + email,
// and receive their AEGIS API key. The github-sponsors function verifies
// the sponsorship is active before provisioning.
import { useState } from 'react'

const SUPABASE_URL  = (import.meta.env.VITE_SUPABASE_URL as string | undefined)
  || 'https://rwehltdwpsncnwxzkwik.supabase.co'
const CLAIM_URL = `${SUPABASE_URL}/functions/v1/github-sponsors/claim`

export function ClaimSponsorPage() {
  const [username, setUsername] = useState('')
  const [email,    setEmail]    = useState('')
  const [apiKey,   setApiKey]   = useState<string | null>(null)
  const [tier,     setTier]     = useState('')
  const [error,    setError]    = useState<string | null>(null)
  const [loading,  setLoading]  = useState(false)

  async function claim() {
    const u = username.trim().replace(/^@/, '')
    const e = email.trim()
    if (!u)              { setError('Enter your GitHub username.'); return }
    if (!e.includes('@')) { setError('Enter a valid email address.'); return }
    setError(null); setLoading(true)
    try {
      const resp = await fetch(CLAIM_URL, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ github_username: u, email: e }),
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.error ?? `HTTP ${resp.status}`)
      setApiKey(data.api_key as string)
      setTier(data.tier as string)
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  if (apiKey) return (
    <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center px-4">
      <div className="max-w-lg w-full">
        <a href="/" className="text-gray-500 text-sm hover:text-gray-300 transition-colors mb-10 block">← aegisomega.com</a>
        <div className="p-6 rounded-lg border border-green-500/30 bg-green-950/20 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            <span className="text-green-400 text-sm font-mono">KEY PROVISIONED — {tier} tier</span>
          </div>
          <p className="text-gray-400 text-sm mb-3">
            Store this securely. Also sent to <strong className="text-white">{email}</strong>.
          </p>
          <div className="bg-gray-900 rounded p-3 border border-gray-700 flex items-center gap-3">
            <code className="text-indigo-300 font-mono text-sm flex-1 break-all">{apiKey}</code>
            <button
              onClick={() => navigator.clipboard.writeText(apiKey)}
              className="text-xs px-3 py-1 rounded border border-gray-600 hover:border-indigo-400 text-gray-300 hover:text-indigo-300 transition-colors shrink-0"
            >Copy</button>
          </div>
        </div>
        <p className="text-gray-500 text-xs text-center">
          Use as <code className="text-gray-400">x-api-key</code> header on every request to{' '}
          <code className="text-gray-400">aegis-vertex.aegisomega.com</code>.
        </p>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center px-4">
      <div className="max-w-md w-full">
        <a href="/" className="text-gray-500 text-sm hover:text-gray-300 transition-colors mb-10 block">← aegisomega.com</a>

        <h1 className="text-2xl font-bold text-white mb-2">Claim your API key</h1>
        <p className="text-gray-400 text-sm mb-8">
          GitHub Sponsors get AEGIS platform access. Enter your GitHub username
          and email to receive your API key.
        </p>

        <div className="space-y-4 mb-6">
          <div>
            <label className="block text-gray-400 text-xs font-mono mb-2 uppercase tracking-wider">GitHub username</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="your-github-username"
              className="w-full bg-gray-900 border border-gray-700 rounded px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500 text-sm font-mono"
            />
          </div>
          <div>
            <label className="block text-gray-400 text-xs font-mono mb-2 uppercase tracking-wider">Email — key delivered here</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full bg-gray-900 border border-gray-700 rounded px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500 text-sm"
            />
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded border border-red-800/60 bg-red-950/20 text-red-400 text-sm">{error}</div>
        )}

        <button
          onClick={claim}
          disabled={loading}
          className="w-full py-3 rounded font-semibold text-sm bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-50 transition-colors"
        >
          {loading ? 'Verifying sponsorship…' : 'Claim API Key →'}
        </button>

        <p className="text-gray-600 text-xs text-center mt-6">
          Not a sponsor?{' '}
          <a href="/pricing" className="text-gray-500 hover:text-gray-300 underline">Purchase access →</a>
        </p>
      </div>
    </div>
  )
}
