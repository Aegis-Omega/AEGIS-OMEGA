import { useMemo, useState, type ReactNode } from 'react'
import { Copy, Download, FlaskConical, RotateCcw, ShieldAlert } from 'lucide-react'
import {
  buildControlledFailureCase,
  formatFailureCaseManifest,
  type ControlledFailureCaseDraftV1,
  type UnsafeRequestedEffect,
} from '../lib/failureCase.js'
import { EXPIRED_APPROVAL_FIXTURE, WRONG_TARGET_FIXTURE } from '../data/failureCaseFixtures.js'

const EMPTY_DRAFT: ControlledFailureCaseDraftV1 = {
  case_id: 'FC-',
  scope: {
    workflow_id: '',
    workflow_version: '',
    environment: 'STAGING',
    action_class: 'DEPLOY',
    target_class: '',
  },
  control: {
    control_point: '',
    authorization_requirement: '',
  },
  test: {
    unauthorized_condition: 'MISSING_APPROVAL',
    fixture_id: 'FIXTURE-',
    preconditions: [],
    input_descriptors: [],
    expected_behavior: 'ACTION_BLOCKED',
  },
  requested_effect: 'NONE',
  evidence_contract: {
    required_observables: [],
    required_artifacts: [],
  },
}

const INPUT_CLASS = 'w-full rounded border border-aegis-border bg-aegis-bg px-3 py-2 text-sm text-aegis-text outline-none focus:border-[#C8A96E]'
const LABEL_CLASS = 'block text-[11px] font-mono uppercase tracking-wide text-aegis-muted mb-1.5'

function splitLines(value: string): string[] {
  return value.split('\n').map(line => line.trim()).filter(Boolean)
}

function joinLines(values: string[]): string {
  return values.join('\n')
}

export function ControlledFailureCaseBuilder() {
  const [draft, setDraft] = useState<ControlledFailureCaseDraftV1>(EMPTY_DRAFT)
  const [copied, setCopied] = useState(false)

  const decision = useMemo(() => buildControlledFailureCase(draft), [draft])
  const manifestText = decision.manifest ? formatFailureCaseManifest(decision.manifest) : ''

  const loadFixture = (fixture: ControlledFailureCaseDraftV1) => {
    setDraft(structuredClone(fixture))
    setCopied(false)
  }

  const reset = () => {
    setDraft(structuredClone(EMPTY_DRAFT))
    setCopied(false)
  }

  const copyManifest = async () => {
    if (!manifestText) return
    await navigator.clipboard.writeText(manifestText)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1500)
  }

  const downloadManifest = () => {
    if (!manifestText || !decision.manifest) return
    const blob = new Blob([manifestText], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${decision.manifest.case_id.toLowerCase()}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  const readinessTone = decision.readiness === 'PACK_READY_FOR_MANUAL_REVIEW'
    ? '#34D399'
    : decision.readiness === 'BLOCKED_UNSAFE_TEST_SCOPE'
      ? '#F87171'
      : '#FBBF24'

  return (
    <div className="flex-1 overflow-y-auto bg-aegis-bg">
      <div className="mx-auto max-w-6xl px-5 py-6">
        <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="mb-1 flex items-center gap-2">
              <FlaskConical size={18} style={{ color: '#C8A96E' }} />
              <h1 className="text-lg font-semibold">Controlled Failure Case Pack</h1>
            </div>
            <p className="max-w-3xl text-sm text-aegis-muted">
              Define a reproducible LOCAL / TEST / STAGING negative case. This surface creates a test definition only; it does not execute actions or grant production authority.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button className="rounded border border-aegis-border px-3 py-2 text-xs text-aegis-muted hover:text-aegis-text" onClick={() => loadFixture(EXPIRED_APPROVAL_FIXTURE)}>
              Load expired-approval example
            </button>
            <button className="rounded border border-aegis-border px-3 py-2 text-xs text-aegis-muted hover:text-aegis-text" onClick={() => loadFixture(WRONG_TARGET_FIXTURE)}>
              Load wrong-target example
            </button>
            <button className="flex items-center gap-1.5 rounded border border-aegis-border px-3 py-2 text-xs text-aegis-muted hover:text-aegis-text" onClick={reset}>
              <RotateCcw size={12} /> Reset
            </button>
          </div>
        </div>

        <div className="mb-5 rounded border border-[#3A2D18] bg-[#17130C] p-3 text-xs text-[#D9BE84]">
          <div className="flex items-start gap-2">
            <ShieldAlert size={15} className="mt-0.5 shrink-0" />
            <span>Hard boundary: no production mutation, real payment, real external message, credential change, or destructive delete can be part of a ready V1 pack.</span>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1.35fr_0.9fr]">
          <div className="space-y-4">
            <Section title="1 · Scope">
              <div className="grid gap-3 md:grid-cols-2">
                <Field label="Case ID">
                  <input className={INPUT_CLASS} value={draft.case_id} onChange={event => setDraft(current => ({ ...current, case_id: event.target.value.toUpperCase() }))} placeholder="FC-EXPIRED-APPROVAL-01" />
                </Field>
                <Field label="Workflow ID">
                  <input className={INPUT_CLASS} value={draft.scope.workflow_id} onChange={event => setDraft(current => ({ ...current, scope: { ...current.scope, workflow_id: event.target.value } }))} placeholder="deployment-agent" />
                </Field>
                <Field label="Workflow version">
                  <input className={INPUT_CLASS} value={draft.scope.workflow_version} onChange={event => setDraft(current => ({ ...current, scope: { ...current.scope, workflow_version: event.target.value } }))} placeholder="staging-v1 or exact source ref" />
                </Field>
                <Field label="Environment">
                  <select className={INPUT_CLASS} value={draft.scope.environment} onChange={event => setDraft(current => ({ ...current, scope: { ...current.scope, environment: event.target.value } }))}>
                    <option value="LOCAL">LOCAL</option>
                    <option value="TEST">TEST</option>
                    <option value="STAGING">STAGING</option>
                  </select>
                </Field>
                <Field label="Action class">
                  <select className={INPUT_CLASS} value={draft.scope.action_class} onChange={event => setDraft(current => ({ ...current, scope: { ...current.scope, action_class: event.target.value } }))}>
                    {['EXTERNAL_MESSAGE', 'REPOSITORY_MUTATION', 'MERGE', 'DEPLOY', 'PRODUCTION_CONFIG', 'FINANCIAL', 'DELETE_DATA', 'IDENTITY_OR_CREDENTIAL', 'OTHER'].map(value => <option key={value} value={value}>{value}</option>)}
                  </select>
                </Field>
                <Field label="Target class">
                  <input className={INPUT_CLASS} value={draft.scope.target_class} onChange={event => setDraft(current => ({ ...current, scope: { ...current.scope, target_class: event.target.value } }))} placeholder="staging service / test repo" />
                </Field>
              </div>
            </Section>

            <Section title="2 · Control boundary">
              <div className="grid gap-3 md:grid-cols-2">
                <Field label="Control point">
                  <input className={INPUT_CLASS} value={draft.control.control_point} onChange={event => setDraft(current => ({ ...current, control: { ...current.control, control_point: event.target.value } }))} placeholder="pre-mutation authority check" />
                </Field>
                <Field label="Authorization requirement">
                  <input className={INPUT_CLASS} value={draft.control.authorization_requirement} onChange={event => setDraft(current => ({ ...current, control: { ...current.control, authorization_requirement: event.target.value } }))} placeholder="approval bound to exact action digest" />
                </Field>
              </div>
            </Section>

            <Section title="3 · Failure injection">
              <div className="grid gap-3 md:grid-cols-2">
                <Field label="Unauthorized condition">
                  <select className={INPUT_CLASS} value={draft.test.unauthorized_condition} onChange={event => setDraft(current => ({ ...current, test: { ...current.test, unauthorized_condition: event.target.value } }))}>
                    {['MISSING_APPROVAL', 'EXPIRED_APPROVAL', 'STALE_APPROVAL', 'WRONG_TARGET', 'WRONG_PARAMETERS', 'REPLAYED_APPROVAL', 'MISSING_POLICY', 'OTHER'].map(value => <option key={value} value={value}>{value}</option>)}
                  </select>
                </Field>
                <Field label="Fixture ID">
                  <input className={INPUT_CLASS} value={draft.test.fixture_id} onChange={event => setDraft(current => ({ ...current, test: { ...current.test, fixture_id: event.target.value.toUpperCase() } }))} placeholder="FIXTURE-EXPIRED-APPROVAL-01" />
                </Field>
                <Field label="Preconditions · one per line">
                  <textarea className={INPUT_CLASS} rows={4} value={joinLines(draft.test.preconditions)} onChange={event => setDraft(current => ({ ...current, test: { ...current.test, preconditions: splitLines(event.target.value) } }))} placeholder="synthetic approval is expired" />
                </Field>
                <Field label="Input descriptors · one per line">
                  <textarea className={INPUT_CLASS} rows={4} value={joinLines(draft.test.input_descriptors)} onChange={event => setDraft(current => ({ ...current, test: { ...current.test, input_descriptors: splitLines(event.target.value) } }))} placeholder="synthetic staging action descriptor" />
                </Field>
              </div>
            </Section>

            <Section title="4 · Expected result and evidence contract">
              <div className="grid gap-3 md:grid-cols-2">
                <Field label="Expected behavior">
                  <select className={INPUT_CLASS} value={draft.test.expected_behavior} onChange={event => setDraft(current => ({ ...current, test: { ...current.test, expected_behavior: event.target.value } }))}>
                    <option value="ACTION_BLOCKED">ACTION_BLOCKED</option>
                    <option value="REQUEST_REJECTED">REQUEST_REJECTED</option>
                    <option value="NO_EXTERNAL_EFFECT">NO_EXTERNAL_EFFECT</option>
                  </select>
                </Field>
                <Field label="Does the test require a real external effect?">
                  <select className={INPUT_CLASS} value={draft.requested_effect} onChange={event => setDraft(current => ({ ...current, requested_effect: event.target.value as UnsafeRequestedEffect }))}>
                    <option value="NONE">NO — synthetic / non-production only</option>
                    <option value="PRODUCTION_MUTATION">Production mutation</option>
                    <option value="REAL_FINANCIAL_EFFECT">Real financial effect</option>
                    <option value="REAL_EXTERNAL_MESSAGE">Real external message</option>
                    <option value="CREDENTIAL_CHANGE">Credential change</option>
                    <option value="DESTRUCTIVE_DELETE">Destructive delete</option>
                  </select>
                </Field>
                <Field label="Required observables · one per line">
                  <textarea className={INPUT_CLASS} rows={4} value={joinLines(draft.evidence_contract.required_observables)} onChange={event => setDraft(current => ({ ...current, evidence_contract: { ...current.evidence_contract, required_observables: splitLines(event.target.value) } }))} placeholder={'decision outcome\ndenial reason\nexternal-effect observation'} />
                </Field>
                <Field label="Required artifacts · one per line">
                  <textarea className={INPUT_CLASS} rows={4} value={joinLines(draft.evidence_contract.required_artifacts)} onChange={event => setDraft(current => ({ ...current, evidence_contract: { ...current.evidence_contract, required_artifacts: splitLines(event.target.value) } }))} placeholder={'decision record\ntested version identifier'} />
                </Field>
              </div>
            </Section>
          </div>

          <div className="lg:sticky lg:top-4 lg:self-start">
            <div className="rounded border border-aegis-border bg-aegis-surface p-4">
              <div className="mb-3 text-xs font-mono uppercase tracking-wide text-aegis-muted">Pack disposition</div>
              <div className="mb-2 text-sm font-semibold" style={{ color: readinessTone }}>{decision.readiness.replaceAll('_', ' ')}</div>

              {decision.reasons.length > 0 && (
                <div className="mb-4 space-y-1 rounded bg-aegis-bg p-3">
                  {decision.reasons.map(reason => <div key={reason} className="font-mono text-[11px] text-aegis-muted">• {reason}</div>)}
                </div>
              )}

              {decision.manifest ? (
                <>
                  <dl className="mb-4 grid grid-cols-[auto_1fr] gap-x-3 gap-y-2 text-xs">
                    <dt className="text-aegis-muted">Case</dt><dd className="font-mono break-all">{decision.manifest.case_id}</dd>
                    <dt className="text-aegis-muted">Environment</dt><dd>{decision.manifest.scope.environment}</dd>
                    <dt className="text-aegis-muted">Expected</dt><dd>{decision.manifest.test.expected_behavior}</dd>
                    <dt className="text-aegis-muted">Executed</dt><dd>NO</dd>
                    <dt className="text-aegis-muted">Production authority</dt><dd>NONE</dd>
                  </dl>

                  <div className="mb-3 flex gap-2">
                    <button onClick={() => void copyManifest()} className="flex items-center gap-1.5 rounded border border-aegis-border px-3 py-2 text-xs hover:border-[#C8A96E]">
                      <Copy size={12} /> {copied ? 'Copied' : 'Copy manifest'}
                    </button>
                    <button onClick={downloadManifest} className="flex items-center gap-1.5 rounded border border-aegis-border px-3 py-2 text-xs hover:border-[#C8A96E]">
                      <Download size={12} /> Download JSON
                    </button>
                  </div>

                  <pre className="max-h-[440px] overflow-auto whitespace-pre-wrap break-words rounded bg-aegis-bg p-3 text-[10px] leading-5 text-aegis-muted">{manifestText}</pre>
                </>
              ) : (
                <p className="text-xs leading-5 text-aegis-muted">Complete the bounded test definition. Unsafe scopes fail closed and never produce a ready pack.</p>
              )}
            </div>

            <div className="mt-3 rounded border border-aegis-border p-3 text-[11px] leading-5 text-aegis-muted">
              <strong className="text-aegis-text">Boundary:</strong> this artifact is a test definition only. It is not evidence that the test ran, not a PASS result, and not permission to mutate production systems.
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded border border-aegis-border bg-aegis-surface p-4">
      <h2 className="mb-4 text-xs font-mono uppercase tracking-wide" style={{ color: '#C8A96E' }}>{title}</h2>
      {children}
    </section>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label>
      <span className={LABEL_CLASS}>{label}</span>
      {children}
    </label>
  )
}
