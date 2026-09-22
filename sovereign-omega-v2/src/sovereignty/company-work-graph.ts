// AEGIS Company Durable Work Graph + Internal Lease V1
// Coordinates dependency-safe internal work. It grants no external authority.

export type CompanyWorkStateV1 =
  | 'PLANNED'
  | 'RUNNING'
  | 'AWAITING_OPERATOR'
  | 'VERIFIED'
  | 'REJECTED'
  | 'CANCELLED'

export interface CompanyWorkNodeV1 {
  readonly task_id: string
  readonly depends_on: readonly string[]
}

export interface CompanyTaskLeaseV1 {
  readonly schema_version: '1.0.0'
  readonly task_id: string
  readonly worker_id: string
  readonly task_digest: string
  readonly acquired_generation: string
  readonly expires_generation: string
  readonly external_authority: 'NOT_GRANTED'
  readonly authority_effect: 'NONE'
  readonly lease_digest: string
}

function text(value: unknown, label: string): string {
  if (typeof value !== 'string' || !value.trim()) throw new TypeError(`${label} must be non-empty`)
  return value
}

function sha(value: unknown, label: string): string {
  if (typeof value !== 'string' || !/^[0-9a-f]{64}$/.test(value)) {
    throw new TypeError(`${label} must be lowercase SHA-256 hex`)
  }
  return value
}

function generation(value: unknown, label: string): bigint {
  const parsed = BigInt(text(value, label))
  if (parsed < 0n) throw new TypeError(`${label} must be non-negative`)
  return parsed
}

function positiveInteger(value: unknown, label: string, max: number): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 1 || value > max) {
    throw new TypeError(`invalid ${label}`)
  }
  return value
}

const STATES: readonly CompanyWorkStateV1[] = [
  'PLANNED', 'RUNNING', 'AWAITING_OPERATOR', 'VERIFIED', 'REJECTED', 'CANCELLED',
]

export function validateCompanyWorkGraphV1(
  input: readonly CompanyWorkNodeV1[],
  maxTasks = 512,
): readonly CompanyWorkNodeV1[] {
  positiveInteger(maxTasks, 'maxTasks', 4096)
  if (!Array.isArray(input)) throw new TypeError('work graph must be an array')
  if (input.length > maxTasks) throw new Error('COMPANY_WORK_GRAPH_TASK_BUDGET_EXCEEDED')

  const nodes = input.map((raw) => {
    const task_id = text(raw?.task_id, 'task_id')
    if (!Array.isArray(raw.depends_on)) throw new TypeError(`depends_on must be array:${task_id}`)
    const depends_on = raw.depends_on.map((dep: string) => text(dep, `dependency:${task_id}`))
    if (new Set(depends_on).size !== depends_on.length) throw new TypeError(`duplicate dependency:${task_id}`)
    if (depends_on.includes(task_id)) throw new TypeError(`self dependency:${task_id}`)
    return Object.freeze({ task_id, depends_on: Object.freeze([...depends_on].sort()) })
  })

  const byId = new Map(nodes.map((node) => [node.task_id, node]))
  if (byId.size !== nodes.length) throw new TypeError('duplicate task_id')
  for (const node of nodes) {
    for (const dep of node.depends_on) {
      if (!byId.has(dep)) throw new TypeError(`missing dependency:${node.task_id}:${dep}`)
    }
  }

  const indegree = new Map(nodes.map((node) => [node.task_id, node.depends_on.length]))
  const children = new Map(nodes.map((node) => [node.task_id, [] as string[]]))
  for (const node of nodes) {
    for (const dep of node.depends_on) children.get(dep)?.push(node.task_id)
  }
  for (const list of children.values()) list.sort()

  const ready = nodes
    .filter((node) => indegree.get(node.task_id) === 0)
    .map((node) => node.task_id)
    .sort()
  const ordered: CompanyWorkNodeV1[] = []
  while (ready.length) {
    const id = ready.shift() as string
    ordered.push(byId.get(id) as CompanyWorkNodeV1)
    for (const child of children.get(id) ?? []) {
      const next = (indegree.get(child) as number) - 1
      indegree.set(child, next)
      if (next === 0) {
        ready.push(child)
        ready.sort()
      }
    }
  }
  if (ordered.length !== nodes.length) throw new Error('COMPANY_WORK_GRAPH_CYCLE')
  return Object.freeze(ordered)
}

function validateStates(
  graph: readonly CompanyWorkNodeV1[],
  states: Readonly<Record<string, CompanyWorkStateV1>>,
): Readonly<Record<string, CompanyWorkStateV1>> {
  if (!states || typeof states !== 'object' || Array.isArray(states)) {
    throw new TypeError('states must be object')
  }
  const ids = new Set(graph.map((node) => node.task_id))
  const keys = Object.keys(states)
  if (keys.length !== ids.size || keys.some((key) => !ids.has(key))) {
    throw new TypeError('state/task domain mismatch')
  }
  for (const id of ids) {
    if (!STATES.includes(states[id])) throw new TypeError(`invalid task state:${id}`)
  }
  return states
}

export function readyCompanyTasksV1(
  graphInput: readonly CompanyWorkNodeV1[],
  statesInput: Readonly<Record<string, CompanyWorkStateV1>>,
  maxReady = 8,
): readonly string[] {
  positiveInteger(maxReady, 'maxReady', 256)
  const graph = validateCompanyWorkGraphV1(graphInput)
  const states = validateStates(graph, statesInput)
  const ready = graph
    .filter((node) => states[node.task_id] === 'PLANNED')
    .filter((node) => node.depends_on.every((dep) => states[dep] === 'VERIFIED'))
    .map((node) => node.task_id)
    .sort()
  return Object.freeze(ready.slice(0, maxReady))
}

export async function createCompanyTaskLeaseV1(
  input: {
    readonly graph: readonly CompanyWorkNodeV1[]
    readonly states: Readonly<Record<string, CompanyWorkStateV1>>
    readonly task_id: string
    readonly worker_id: string
    readonly task_digest: string
    readonly current_generation: string
    readonly ttl_generations: number
    readonly max_ttl_generations?: number
  },
  hash: (domain: string, value: unknown) => Promise<string>,
): Promise<CompanyTaskLeaseV1> {
  const task_id = text(input?.task_id, 'task_id')
  const worker_id = text(input?.worker_id, 'worker_id')
  const task_digest = sha(input?.task_digest, 'task_digest')
  const current = generation(input?.current_generation, 'current_generation')
  const maxTtl = positiveInteger(
    input.max_ttl_generations ?? 16,
    'max_ttl_generations',
    1024,
  )
  const ttl = positiveInteger(input?.ttl_generations, 'ttl_generations', maxTtl)
  const ready = readyCompanyTasksV1(input.graph, input.states, 256)
  if (!ready.includes(task_id)) throw new Error('COMPANY_TASK_NOT_READY_FOR_LEASE')

  const body = Object.freeze({
    schema_version: '1.0.0' as const,
    task_id,
    worker_id,
    task_digest,
    acquired_generation: current.toString(),
    expires_generation: (current + BigInt(ttl)).toString(),
    external_authority: 'NOT_GRANTED' as const,
    authority_effect: 'NONE' as const,
  })
  const lease_digest = sha(
    await hash('AEGIS_COMPANY_TASK_LEASE_V1', body),
    'lease_digest',
  )
  return Object.freeze({ ...body, lease_digest })
}

export async function verifyCompanyTaskLeaseV1(
  lease: CompanyTaskLeaseV1,
  expectedTaskDigest: string,
  currentGeneration: string,
  hash: (domain: string, value: unknown) => Promise<string>,
): Promise<boolean> {
  const expected = sha(expectedTaskDigest, 'expected task_digest')
  const current = generation(currentGeneration, 'current_generation')
  const acquired = generation(lease?.acquired_generation, 'acquired_generation')
  const expires = generation(lease?.expires_generation, 'expires_generation')
  if (current < acquired || current > expires) return false
  if (lease.task_digest !== expected) return false
  if (
    lease.external_authority !== 'NOT_GRANTED' ||
    lease.authority_effect !== 'NONE'
  ) return false

  const body = {
    schema_version: lease.schema_version,
    task_id: text(lease.task_id, 'task_id'),
    worker_id: text(lease.worker_id, 'worker_id'),
    task_digest: sha(lease.task_digest, 'task_digest'),
    acquired_generation: lease.acquired_generation,
    expires_generation: lease.expires_generation,
    external_authority: lease.external_authority,
    authority_effect: lease.authority_effect,
  }
  return sha(
    await hash('AEGIS_COMPANY_TASK_LEASE_V1', body),
    'recomputed lease_digest',
  ) === sha(lease.lease_digest, 'lease_digest')
}
