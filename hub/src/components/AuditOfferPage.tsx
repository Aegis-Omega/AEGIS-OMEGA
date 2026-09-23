import { useMemo, useState } from 'react'
import {
  ArrowRight,
  CheckCircle2,
  FileSearch,
  GitBranch,
  LockKeyhole,
  ShieldCheck,
  Wrench,
} from 'lucide-react'
import '../audit-offer.css'

type FormState = {
  workflow: string
  authority: string
  controls: string
  evidence: string
  timeline: string
}

const EMPTY_FORM: FormState = {
  workflow: '',
  authority: '',
  controls: '',
  evidence: '',
  timeline: '',
}

const DELIVERABLES = [
  ['01', 'Authority surface map', 'Agents, tools, identities, privileged actions, and where authority enters the workflow.'],
  ['02', 'Pre-mutation control review', 'Approval paths and checks immediately before consequential state change.'],
  ['03', 'Fail-open / fail-closed gap register', 'Concrete places where missing evidence, policy, or runtime state can silently widen authority.'],
  ['04', 'Audit-lineage assessment', 'What can be bound to durable receipts, replayed, and independently inspected.'],
  ['05', 'Prioritized remediation plan', 'Smallest engineering changes first, separated from larger architectural work.'],
  ['06', 'Executive + engineering report', 'Decision-ready summary backed by a technical evidence appendix.'],
] as const

const BOUNDARIES = [
  'No claim of universal production enforcement.',
  'No compliance certification or legal opinion.',
  'No claim that every agent action enters consensus or a single runtime path.',
  'Research-frontier work is not presented as commercial proof.',
] as const

export function AuditOfferPage() {
  const [form, setForm] = useState<FormState>(EMPTY_FORM)

  const mailto = useMemo(() => {
    const subject = 'AEGIS Agent Action Boundary Audit — workflow'
    const body = [
      'I want to scope one agentic workflow for the AEGIS Agent Action Boundary Audit.',
      '',
      '1. What the workflow does:',
      form.workflow || '[describe workflow]',
      '',
      '2. Highest-authority action:',
      form.authority || '[read / write / provision / spend / access change / other]',
      '',
      '3. Current approval or policy controls:',
      form.controls || '[describe current controls]',
      '',
      '4. Current evidence / audit trail:',
      form.evidence || '[logs / receipts / replay / none / unsure]',
      '',
      '5. Target timeline:',
      form.timeline || '[timeline]',
      '',
      'Please reply with fit, scope boundary, required evidence, and next step.',
    ].join('\n')

    return `mailto:info@aegisomega.com?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
  }, [form])

  const setField = (key: keyof FormState, value: string) => {
    setForm(current => ({ ...current, [key]: value }))
  }

  return (
    <main className="audit-page">
      <header className="audit-topbar">
        <a className="audit-brand" href="/" aria-label="Aegis Omega home">
          <span className="audit-mark">Ω</span>
          <span>AEGIS OMEGA LABS</span>
        </a>
        <nav className="audit-nav" aria-label="Audit navigation">
          <a href="#scope">Scope</a>
          <a href="#deliverables">Deliverables</a>
          <a href="#qualify">Qualify</a>
        </nav>
        <a className="audit-top-cta" href="#qualify">Send one workflow</a>
      </header>

      <section className="audit-hero">
        <div className="audit-wrap audit-hero-grid">
          <div>
            <div className="audit-kicker">Founder pilot · one bounded workflow</div>
            <h1>
              Find where your AI agent
              <span> actually gets authority.</span>
            </h1>
            <p className="audit-lead">
              A fixed-fee technical audit for teams deploying tool-using AI.
              We trace one workflow from request to consequential action, identify
              evidence and authority gaps, and return a bounded remediation plan.
            </p>

            <div className="audit-price-row">
              <div>
                <span className="audit-price">$3,000</span>
                <span className="audit-price-note">fixed fee</span>
              </div>
              <div className="audit-price-divider" />
              <div>
                <span className="audit-price">1</span>
                <span className="audit-price-note">agentic workflow</span>
              </div>
              <div className="audit-price-divider" />
              <div>
                <span className="audit-price">5</span>
                <span className="audit-price-note">business-day target</span>
              </div>
            </div>

            <div className="audit-actions">
              <a className="audit-btn audit-btn-primary" href="#qualify">
                Send one workflow <ArrowRight size={17} />
              </a>
              <a className="audit-btn audit-btn-ghost" href="#deliverables">
                See what you get
              </a>
            </div>
          </div>

          <aside className="audit-signal-card" aria-label="Audit model">
            <div className="audit-signal-head">
              <ShieldCheck size={18} />
              <span>BOUNDARY MODEL</span>
            </div>
            <div className="audit-path">
              <div><span>01</span><b>REQUEST</b><small>what the agent intends</small></div>
              <div className="audit-path-line" />
              <div><span>02</span><b>AUTHORITY</b><small>what is permitted and by whom</small></div>
              <div className="audit-path-line" />
              <div><span>03</span><b>MUTATION</b><small>where state can actually change</small></div>
              <div className="audit-path-line" />
              <div><span>04</span><b>EVIDENCE</b><small>what can be verified afterward</small></div>
            </div>
            <div className="audit-signal-foot">
              The audit looks for mismatches between these four states.
            </div>
          </aside>
        </div>
      </section>

      <section id="scope" className="audit-section audit-section-alt">
        <div className="audit-wrap">
          <div className="audit-section-head">
            <div className="audit-kicker">Scope</div>
            <h2>Not a generic AI safety review.</h2>
            <p>
              The engagement is deliberately narrow: one workflow with real tools,
              permissions, approvals, and evidence paths.
            </p>
          </div>

          <div className="audit-three">
            <article>
              <LockKeyhole size={21} />
              <h3>Authority</h3>
              <p>Who or what can authorize consequential actions, and where that authority is technically enforced.</p>
            </article>
            <article>
              <GitBranch size={21} />
              <h3>Execution path</h3>
              <p>What happens between model output and mutation, including wrappers, queues, tools, and approval gates.</p>
            </article>
            <article>
              <FileSearch size={21} />
              <h3>Evidence</h3>
              <p>Which transitions are logged, receipt-bound, replayable, or unverifiable from the artifacts available today.</p>
            </article>
          </div>
        </div>
      </section>

      <section id="deliverables" className="audit-section">
        <div className="audit-wrap">
          <div className="audit-section-head">
            <div className="audit-kicker">Deliverables</div>
            <h2>Six outputs. One decision-ready package.</h2>
          </div>

          <div className="audit-deliverables">
            {DELIVERABLES.map(([num, title, copy]) => (
              <article key={num}>
                <span className="audit-num">{num}</span>
                <div>
                  <h3>{title}</h3>
                  <p>{copy}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="audit-section audit-section-alt">
        <div className="audit-wrap audit-boundary-grid">
          <div>
            <div className="audit-kicker">Claims boundary</div>
            <h2>Evidence first. No inflated assurance.</h2>
            <p>
              Findings are scoped to the workflow and evidence actually reviewed.
              The report separates direct observation from inference and from open gaps.
            </p>
          </div>
          <div className="audit-boundary-list">
            {BOUNDARIES.map(item => (
              <div key={item}>
                <CheckCircle2 size={17} />
                <span>{item}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="qualify" className="audit-section">
        <div className="audit-wrap audit-qualify-grid">
          <div className="audit-section-head audit-section-head-sticky">
            <div className="audit-kicker">Qualification</div>
            <h2>Send the workflow, not a deck.</h2>
            <p>
              Five short answers are enough to decide whether the audit is a fit.
              Nothing is submitted automatically; the button opens your mail client
              with the answers prefilled.
            </p>
            <div className="audit-fit">
              <Wrench size={18} />
              <span>
                Best fit: agents that can write state, call consequential APIs,
                provision resources, alter access, or initiate financial actions.
              </span>
            </div>
          </div>

          <form className="audit-form" onSubmit={event => event.preventDefault()}>
            <label>
              <span>1. What does the workflow do?</span>
              <textarea
                value={form.workflow}
                onChange={e => setField('workflow', e.target.value)}
                placeholder="Example: triages support requests and can update customer records."
              />
            </label>
            <label>
              <span>2. What is the highest-authority action?</span>
              <input
                value={form.authority}
                onChange={e => setField('authority', e.target.value)}
                placeholder="Write DB state, provision cloud, modify access, initiate spend..."
              />
            </label>
            <label>
              <span>3. What controls exist before that action?</span>
              <textarea
                value={form.controls}
                onChange={e => setField('controls', e.target.value)}
                placeholder="Policy engine, human approval, wrapper API, allowlist, none..."
              />
            </label>
            <label>
              <span>4. What evidence exists today?</span>
              <textarea
                value={form.evidence}
                onChange={e => setField('evidence', e.target.value)}
                placeholder="Logs, receipts, replay records, traces, screenshots, unsure..."
              />
            </label>
            <label>
              <span>5. What is your timeline?</span>
              <input
                value={form.timeline}
                onChange={e => setField('timeline', e.target.value)}
                placeholder="Already live, 30 days, before enterprise launch..."
              />
            </label>

            <a className="audit-btn audit-btn-primary audit-submit" href={mailto}>
              Open email with answers <ArrowRight size={17} />
            </a>
            <small>
              Recipient: info@aegisomega.com · No form data is transmitted by this page.
            </small>
          </form>
        </div>
      </section>

      <footer className="audit-footer">
        <div className="audit-wrap">
          <span>AEGIS OMEGA LABS</span>
          <span>Agent Action Boundary Audit · Founder Pilot</span>
        </div>
      </footer>
    </main>
  )
}
