// AEGIS Autonomous Company Control Loop V1
// Deterministic orchestration; intelligence may propose work but cannot grant authority.

export type CompanyActionClassV1 =
  | 'RESEARCH_READ' | 'ANALYZE' | 'DRAFT' | 'LOCAL_SANDBOX_WRITE' | 'TEST' | 'EVAL' | 'PROPOSE'
  | 'EXTERNAL_MESSAGE' | 'REPOSITORY_MUTATION' | 'MERGE' | 'DEPLOY' | 'PRODUCTION_CONFIG'
  | 'FINANCIAL' | 'LEGAL_COMMITMENT' | 'DELETE_DATA' | 'IDENTITY_OR_CREDENTIAL'
export interface CompanyTaskV1 {
  readonly task_id: string
  readonly department: string
  readonly objective: string
  readonly action_class: CompanyActionClassV1
}
export interface CompanyExecutionV1 { readonly output: string; readonly evidence: Readonly<Record<string, unknown>> }
export interface CompanyVerificationV1 { readonly verdict: 'PASS' | 'FAIL'; readonly reason: string }

const AUTO = new Set<CompanyActionClassV1>([
  'RESEARCH_READ', 'ANALYZE', 'DRAFT', 'LOCAL_SANDBOX_WRITE', 'TEST', 'EVAL', 'PROPOSE',
])
const ALL = new Set<CompanyActionClassV1>([
  ...AUTO, 'EXTERNAL_MESSAGE', 'REPOSITORY_MUTATION', 'MERGE', 'DEPLOY', 'PRODUCTION_CONFIG',
  'FINANCIAL', 'LEGAL_COMMITMENT', 'DELETE_DATA', 'IDENTITY_OR_CREDENTIAL',
])
function text(v: unknown, label: string): string {
  if (typeof v !== 'string' || !v.trim()) throw new TypeError(label + ' must be non-empty')
  return v
}
function hash(v: string, label: string): string {
  if (!/^[0-9a-f]{64}$/.test(v)) throw new TypeError(label + ' must be lowercase SHA-256 hex')
  return v
}
function task(v: CompanyTaskV1): CompanyTaskV1 {
  text(v?.task_id, 'task_id'); text(v?.department, 'department'); text(v?.objective, 'task objective')
  if (!ALL.has(v.action_class)) throw new TypeError('invalid action_class')
  return v
}

export function isAutonomousCompanyActionV1(action: CompanyActionClassV1): boolean { return AUTO.has(action) }

export function createAutonomousCompanyLoopV1(options: {
  readonly planner: { plan(objective: string): Promise<{ readonly tasks: readonly CompanyTaskV1[] }> }
  readonly executor: { execute(task: CompanyTaskV1): Promise<CompanyExecutionV1> }
  readonly verifier: { verify(task: CompanyTaskV1, execution: CompanyExecutionV1): Promise<CompanyVerificationV1> }
  readonly authorize?: (task: CompanyTaskV1) => boolean | Promise<boolean>
  readonly hash: (domain: string, value: unknown) => Promise<string>
  readonly max_tasks?: number
}) {
  if (typeof options?.planner?.plan !== 'function' || typeof options?.executor?.execute !== 'function' ||
      typeof options?.verifier?.verify !== 'function' || typeof options?.hash !== 'function') throw new TypeError('company loop dependencies required')
  const maxTasks = options.max_tasks ?? 64
  if (!Number.isSafeInteger(maxTasks) || maxTasks < 1 || maxTasks > 512) throw new TypeError('invalid max_tasks')
  const authorize = options.authorize ?? (() => false)

  return Object.freeze({
    async run(rawObjective: string) {
      const objective = text(rawObjective, 'company objective')
      const plan = await options.planner.plan(objective)
      if (!plan || !Array.isArray(plan.tasks)) throw new TypeError('planner must return tasks')
      if (plan.tasks.length > maxTasks) throw new Error('COMPANY_TASK_BUDGET_EXCEEDED')
      const tasks = plan.tasks.map(v => Object.freeze({ ...task(structuredClone(v)) }))
      const ids = new Set<string>()
      for (const item of tasks) {
        if (ids.has(item.task_id)) throw new Error('DUPLICATE_COMPANY_TASK_ID:' + item.task_id)
        ids.add(item.task_id)
      }

      const receipts: Array<Readonly<Record<string, unknown>>> = []
      for (const item of tasks) {
        const granted = AUTO.has(item.action_class) || await authorize(item) === true
        if (!granted) {
          receipts.push(Object.freeze({ task_id:item.task_id, department:item.department, action_class:item.action_class,
            status:'AWAITING_OPERATOR', execution_hash:null, verification_hash:null, authority_effect:'NONE' }))
          continue
        }
        const execution = await options.executor.execute(item)
        const executionHash = hash(await options.hash('AEGIS_COMPANY_EXECUTION_V1', { item, execution }), 'execution_hash')
        const verification = await options.verifier.verify(item, execution)
        if (!['PASS', 'FAIL'].includes(verification.verdict)) throw new TypeError('invalid verifier verdict')
        const verificationHash = hash(await options.hash('AEGIS_COMPANY_VERIFICATION_V1', {
          task_id:item.task_id, execution_hash:executionHash, verdict:verification.verdict, reason:verification.reason,
        }), 'verification_hash')
        receipts.push(Object.freeze({ task_id:item.task_id, department:item.department, action_class:item.action_class,
          status:verification.verdict === 'PASS' ? 'VERIFIED' : 'REJECTED', execution_hash:executionHash,
          verification_hash:verificationHash, authority_effect:'NONE' }))
      }
      const completed = receipts.filter(r => r.status === 'VERIFIED').length
      const rejected = receipts.filter(r => r.status === 'REJECTED').length
      const awaiting = receipts.filter(r => r.status === 'AWAITING_OPERATOR').length
      const body = Object.freeze({ schema_version:'1.0.0', objective, task_receipts:Object.freeze(receipts),
        completed, rejected, awaiting_operator:awaiting, authority_effect:'NONE' as const })
      const receiptRoot = hash(await options.hash('AEGIS_AUTONOMOUS_COMPANY_RUN_V1', body), 'receipt_root')
      return Object.freeze({ ...body, receipt_root:receiptRoot })
    },
  })
}
