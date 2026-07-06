// AEGIS-Ω Platform API Reference — /docs
// Single-page API reference. Full NOUS nav + interaction language.
import { useState } from 'react'
import { T, MONO } from './console/consoleTokens.js'
import { NousButton, ArrowR } from './console/NousUI.js'

const BASE = 'https://aegis-vertex.aegisomega.com'

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000) }) }}
      className="text-xs px-2 py-0.5 rounded border border-gray-600 hover:border-indigo-400 text-gray-400 hover:text-indigo-300 transition-colors flex-shrink-0"
    >
      {copied ? '✓' : 'copy'}
    </button>
  )
}

function CodeBlock({ code, lang = 'bash' }: { code: string; lang?: string }) {
  return (
    <div className="relative bg-gray-950 rounded-lg border border-gray-800 p-4 mt-3">
      <div className="absolute top-2 right-2 flex items-center gap-2">
        <span className="text-gray-600 text-xs font-mono">{lang}</span>
        <CopyButton text={code} />
      </div>
      <pre className="text-xs text-gray-300 font-mono leading-relaxed overflow-x-auto whitespace-pre">{code}</pre>
    </div>
  )
}

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} style={{ marginBottom: 64, scrollMarginTop: 80 }}>
      <h2 style={{
        fontSize: 20, fontWeight: 700, color: T.text, marginBottom: 24,
        paddingBottom: 14, borderBottom: `1px solid ${T.border}`,
      }}>{title}</h2>
      {children}
    </section>
  )
}

function Endpoint({
  method, path, auth, desc, request, response, notes,
}: {
  method: 'GET' | 'POST' | 'DELETE'
  path: string
  auth: boolean
  desc: string
  request?: string
  response: string
  notes?: string
}) {
  const methodColor = method === 'GET' ? '#34D399' : method === 'POST' ? '#818CF8' : '#F87171'
  return (
    <div className="mb-10 bg-gray-900/50 border border-gray-800 rounded-lg overflow-hidden">
      <div className="px-5 py-4 flex items-start gap-4 border-b border-gray-800">
        <span className="text-xs font-bold px-2 py-1 rounded mt-0.5 flex-shrink-0"
          style={{ background: `${methodColor}18`, color: methodColor, border: `1px solid ${methodColor}40` }}>
          {method}
        </span>
        <div className="flex-1 min-w-0">
          <code className="text-white font-mono text-sm">{BASE}{path}</code>
          {auth && (
            <span className="ml-3 text-xs px-2 py-0.5 rounded" style={{ background: 'rgba(245,158,11,0.12)', color: '#F59E0B', border: '1px solid rgba(245,158,11,0.25)' }}>
              x-api-key required
            </span>
          )}
          <p className="text-gray-400 text-sm mt-1">{desc}</p>
        </div>
      </div>
      <div className="px-5 py-4 space-y-4">
        {request && (
          <div>
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Request body</div>
            <CodeBlock code={request} lang="json" />
          </div>
        )}
        <div>
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Response</div>
          <CodeBlock code={response} lang="json" />
        </div>
        {notes && (
          <p className="text-xs text-gray-500 leading-relaxed">{notes}</p>
        )}
      </div>
    </div>
  )
}

const NAV_ITEMS = [
  { id: 'overview',      label: 'Overview' },
  { id: 'auth',          label: 'Authentication' },
  { id: 'collaborate',   label: 'POST /collaborate' },
  { id: 'status',        label: 'GET /status' },
  { id: 'executions',    label: 'Async executions' },
  { id: 'sse',           label: 'SSE stream' },
  { id: 'errors',        label: 'Error codes' },
  { id: 'contract',      label: 'Contract version' },
]

export function DocsPage() {
  const links: [string, string][] = [['/', 'Home'], ['/platform', 'Platform'], ['/console', 'Console'], ['/docs', 'Docs'], ['/pricing', 'Pricing']]

  return (
    <div className="min-h-screen text-white" style={{ background: '#06070C', fontFamily: 'var(--font-sans)' }}>
      {/* NOUS Nav */}
      <nav style={{
        position: 'sticky', top: 0, zIndex: 50,
        background: 'rgba(6,7,12,0.55)', backdropFilter: 'blur(16px) saturate(150%)',
        borderBottom: `1px solid rgba(255,255,255,0.06)`,
      }} className="px-7 py-4 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <a href="/" style={{ color: T.text, fontFamily: MONO, letterSpacing: '0.22em', fontSize: 13, fontWeight: 600 }}>
            NOUS<span style={{ color: T.phi }}> · Ω</span>
          </a>
          <div className="hidden md:flex items-center gap-7">
            {links.map(([href, label]) => (
              <a key={href} href={href} style={{
                color: href === '/docs' ? T.text : T.muted, fontSize: 13,
                fontWeight: href === '/docs' ? 600 : 400, textDecoration: 'none',
              }} className="hover:text-white transition-colors">{label}</a>
            ))}
          </div>
        </div>
        <NousButton href="/pricing" variant="primary" size="md">Get API Key <ArrowR /></NousButton>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-12 flex gap-12">
        {/* Sidebar */}
        <aside className="hidden lg:block w-48 flex-shrink-0">
          <nav className="sticky top-24 space-y-0.5">
            {NAV_ITEMS.map(item => (
              <a key={item.id} href={`#${item.id}`} style={{
                display: 'block', fontSize: 13, padding: '7px 10px', borderRadius: 7,
                color: T.muted, textDecoration: 'none', transition: 'color 0.15s, background 0.15s',
              }} className="hover:!text-white hover:!bg-white/5">
                {item.label}
              </a>
            ))}
            <div style={{ marginTop: 24, padding: '0 10px' }}>
              <NousButton href="/pricing" variant="primary" size="md" style={{ width: '100%', justifyContent: 'center', fontSize: 12 }}>
                Get key <ArrowR />
              </NousButton>
            </div>
          </nav>
        </aside>

        {/* Content */}
        <main className="flex-1 min-w-0">
          <Section id="overview" title="Overview">
            <p className="text-gray-400 leading-relaxed mb-4">
              The AEGIS-Ω Platform API provides access to 39 autonomous agent departments that collaborate
              on any business objective. Every response is SHA-256 hash-chained, replay-verifiable, and
              includes a constitutional audit verdict.
            </p>
            <div className="grid grid-cols-2 gap-4 mt-6">
              {[
                { k: 'Base URL',          v: BASE },
                { k: 'Contract version',  v: '1.0.0' },
                { k: 'Auth header',       v: 'x-api-key' },
                { k: 'Response format',   v: 'application/json' },
              ].map(row => (
                <div key={row.k} className="bg-gray-900 rounded-lg p-4 border border-gray-800">
                  <div className="text-xs text-gray-500 mb-1">{row.k}</div>
                  <code className="text-sm text-indigo-300 font-mono">{row.v}</code>
                </div>
              ))}
            </div>
          </Section>

          <Section id="auth" title="Authentication">
            <p className="text-gray-400 mb-4">
              Every request (except <code className="text-gray-300 text-xs">GET /platform/status</code>) requires
              an API key passed as the <code className="text-gray-300 text-xs">x-api-key</code> header.
              Keys are prefixed <code className="text-gray-300 text-xs">aegis_</code> and issued immediately after purchase.
            </p>
            <CodeBlock code={`curl -H "x-api-key: aegis_YOUR_KEY" ${BASE}/platform/status`} />
            <div className="mt-6 grid grid-cols-3 gap-3">
              {[
                { tier: 'Explorer', price: 'Free',  runs: '10',       color: '#6B7280' },
                { tier: 'Operator', price: '$49',   runs: '500',      color: '#818CF8' },
                { tier: 'Sovereign',price: '$499',  runs: 'Unlimited',color: '#F59E0B' },
              ].map(t => (
                <div key={t.tier} className="bg-gray-900 rounded-lg p-4 border border-gray-800">
                  <div className="text-xs font-semibold mb-1" style={{ color: t.color }}>{t.tier}</div>
                  <div className="text-lg font-bold text-white">{t.price}</div>
                  <div className="text-xs text-gray-500 mt-1">{t.runs} governed runs</div>
                </div>
              ))}
            </div>
            <p className="text-xs text-gray-600 mt-3">
              One run = one successful <code className="text-gray-500">POST /platform/collaborate</code>.
              Runs are never charged for failed or rejected requests.
            </p>
          </Section>

          <Section id="collaborate" title="POST /platform/collaborate">
            <p className="text-gray-400 mb-2">
              Run a full 39-agent collaboration cycle synchronously. Returns the complete result when all departments have
              contributed. Typical response time: 2–8 seconds in demo mode.
            </p>
            <Endpoint
              method="POST"
              path="/platform/collaborate"
              auth={true}
              desc="Synchronous 39-agent collaboration. Returns CollaborationResult wrapped in PlatformEnvelope."
              request={`{
  "objective": "Enter EU fintech market Q4 2026",
  "mode": "gtm",      // "revenue" | "analysis" | "gtm" | "retention"
  "live": false       // true = live Claude inference; false = demo mode
}`}
              response={`{
  "contract_version": "1.0.0",
  "execution_id": "018f4a2c-...",
  "timestamp": "2026-06-07T03:30:00.000Z",
  "is_replay_reconstructable": true,
  "data": {
    "cycle_id": "018f4a2c-...",
    "objective": "Enter EU fintech market Q4 2026",
    "mode": "gtm",
    "departments_collaborated": 39,
    "artifacts": [
      { "role": "Strategy", "output": "GTM for \"Enter EU fintech...\" — 4-phase launch..." },
      // ... 38 more department outputs
    ],
    "projection": {
      "first_year_arr_usd": 2400000,
      "tier": "operator"
    },
    "constitutional_audit": {
      "verdict": "APPROVED",
      "concerns": []
    },
    "chain_valid": true,
    "audit_chain_hash": "sha256:a3f9...",
    "execution_id": "018f4a2c-..."
  }
}`}
              notes="Available modes: revenue (monetisation vectors), analysis (market research), gtm (go-to-market phases), retention (churn reduction). All responses include audit_chain_hash — cryptographic proof of the run."
            />
          </Section>

          <Section id="status" title="GET /platform/status">
            <p className="text-gray-400 mb-4">
              Public health check. No authentication required. Returns runtime version, chain integrity,
              and agent count.
            </p>
            <Endpoint
              method="GET"
              path="/platform/status"
              auth={false}
              desc="Runtime health check. Public — no API key needed."
              response={`{
  "contract_version": "1.0.0",
  "execution_id": "018f4a2c-...",
  "timestamp": "2026-06-07T03:30:00.000Z",
  "is_replay_reconstructable": true,
  "data": {
    "version": "1.0.0",
    "contract_version": "1.0.0",
    "total_agents": 39,
    "chain_valid": true,
    "audit_chain_hash": "sha256:...",
    "available": true
  }
}`}
            />
          </Section>

          <Section id="executions" title="Async Executions">
            <p className="text-gray-400 mb-4">
              For long-running collaborations or real-time UIs, start an async execution and stream
              per-agent events as they complete.
            </p>
            <Endpoint
              method="POST"
              path="/platform/executions"
              auth={true}
              desc="Initiate an async collaboration. Returns immediately with an execution_id and stream URL."
              request={`{
  "objective": "Reduce churn in SMB segment",
  "mode": "retention",
  "live": false
}`}
              response={`{
  "execution_id": "018f4a2c-...",
  "stream_url": "/platform/executions/live?id=018f4a2c-..."
}`}
            />
            <Endpoint
              method="GET"
              path="/platform/executions/{execution_id}"
              auth={true}
              desc="Retrieve a completed execution result by ID. Returns 404 if not found or expired."
              response={`{
  "contract_version": "1.0.0",
  "execution_id": "018f4a2c-...",
  "timestamp": "...",
  "is_replay_reconstructable": true,
  "data": { /* CollaborationResult — same shape as /collaborate */ }
}`}
            />
            <Endpoint
              method="DELETE"
              path="/platform/executions/{execution_id}"
              auth={true}
              desc="Remove a stored execution result. Returns 204 on success."
              response={`204 No Content`}
            />
          </Section>

          <Section id="sse" title="SSE Event Stream">
            <p className="text-gray-400 mb-4">
              After starting an async execution, connect to the stream URL to receive real-time
              per-agent events as each of the 39 departments completes.
            </p>
            <CodeBlock code={`curl -N "${BASE}/platform/executions/live?id=EXECUTION_ID" \\
  -H "Accept: text/event-stream"`} />
            <div className="mt-4 space-y-3">
              {[
                { type: 'dag_step',    payload: '{ dept_id, dept_name, category, step_index, total_steps }',  desc: 'Emitted as each department starts' },
                { type: 'agent_event', payload: '{ dept_id, role, output_preview: string(120) }',             desc: 'Department output preview (first 120 chars)' },
                { type: 'tool_call',   payload: '{ tool_name, args_hash }',                                    desc: 'Internal tool invocation (live mode)' },
                { type: 'heartbeat',   payload: '{ }',                                                         desc: 'Sent every 15s to keep connection alive' },
                { type: 'error',       payload: '{ code, message }',                                           desc: 'Stream-level error' },
                { type: 'completion',  payload: '{ /* CollaborationResult */ }',                               desc: 'Final event — full result' },
              ].map(ev => (
                <div key={ev.type} className="flex items-start gap-4 bg-gray-900 rounded-lg p-3 border border-gray-800 text-xs">
                  <code className="text-indigo-300 font-mono flex-shrink-0 w-28">{ev.type}</code>
                  <code className="text-gray-400 font-mono flex-1">{ev.payload}</code>
                  <span className="text-gray-600 flex-shrink-0 w-48 text-right">{ev.desc}</span>
                </div>
              ))}
            </div>
            <p className="text-xs text-gray-600 mt-4">
              Each event is a JSON object with fields: <code className="text-gray-500">type</code>,{' '}
              <code className="text-gray-500">execution_id</code>,{' '}
              <code className="text-gray-500">timestamp</code>,{' '}
              <code className="text-gray-500">payload</code>.
            </p>
          </Section>

          <Section id="errors" title="Error Codes">
            <div className="space-y-2">
              {[
                { code: '401', name: 'UNAUTHORIZED',    desc: 'Missing or invalid API key' },
                { code: '400', name: 'INVALID_REQUEST', desc: 'Malformed request body — check objective, mode, live fields' },
                { code: '429', name: 'RATE_LIMITED',    desc: 'Run limit reached for your tier — upgrade or wait' },
                { code: '404', name: 'NOT_FOUND',       desc: 'Execution ID not found or expired' },
                { code: '500', name: 'INTERNAL',        desc: 'Bridge error — contact info@aegisomega.com' },
              ].map(err => (
                <div key={err.code} className="flex items-start gap-4 bg-gray-900 rounded-lg p-3 border border-gray-800 text-xs">
                  <code className="text-red-400 font-mono font-bold w-10 flex-shrink-0">{err.code}</code>
                  <code className="text-orange-300 font-mono w-32 flex-shrink-0">{err.name}</code>
                  <span className="text-gray-400">{err.desc}</span>
                </div>
              ))}
            </div>
            <CodeBlock lang="json" code={`{
  "error": "Invalid or revoked API key",
  "code": "UNAUTHORIZED",
  "execution_id": "018f4a2c-..."  // present when applicable
}`} />
          </Section>

          <Section id="contract" title="Contract Version">
            <p className="text-gray-400 mb-4">
              Every response includes <code className="text-gray-300 text-xs">contract_version: "1.0.0"</code> and
              an <code className="text-gray-300 text-xs">X-Contract-Version</code> response header.
              Breaking changes increment the version and add a <code className="text-gray-300 text-xs">/platform/v2/*</code> prefix.
              The current <code className="text-gray-300 text-xs">/platform/*</code> prefix aliases v1 until deprecated.
            </p>
            <div className="bg-gray-900 rounded-lg p-4 border border-gray-800 text-xs font-mono" style={{ color: '#94A3B8' }}>
              <div style={{ color: '#C8A96E' }}>X-Contract-Version: 1.0.0</div>
              <div style={{ color: '#818CF8' }}>X-Git-SHA: {'<build sha>'}</div>
              <div className="mt-2" style={{ color: '#34D399' }}>is_replay_reconstructable: true  // always</div>
            </div>
            <p className="text-xs text-gray-600 mt-4">
              Questions or integration help:{' '}
              <a href="mailto:info@aegisomega.com" className="text-gray-500 hover:text-gray-400 underline">
                info@aegisomega.com
              </a>
            </p>
          </Section>
        </main>
      </div>
    </div>
  )
}
