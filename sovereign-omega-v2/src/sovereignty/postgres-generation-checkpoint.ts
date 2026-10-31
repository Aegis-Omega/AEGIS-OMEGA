/**
 * Fixed-query PostgreSQL checkpoint bridge for authenticated trusted hosts.
 *
 * Read-only on the JS side: the sole allowed SQL is a parameterized call to
 * the server's atomic, privilege-restricted generation checkpoint routine.
 * The SQL routine may update a high-water mark; it must be independently
 * audited, durable, transaction-committing and permission-gated.
 *
 * This module does NOT create connections, use secrets, auto-bootstrap rows,
 * reserve provider quota, or authorize spending/execution.
 */
import type { AuthenticatedAtomicGenerationCheckpointV1 } from './durable-free-resource-planner.js'

const POLICY_ID=/^[a-zA-Z0-9._:-]{1,128}$/
const DEC=/^(0|[1-9][0-9]*)$/
const FUNCTION_SQL=
  'SELECT outcome, persisted_generation '+
  'FROM public.aegis_test_observe_advance_v1($1::text,$2::text)'

export interface AuthenticatedParameterizedPostgresV1 {
  /** Host-authenticated role with EXECUTE on the approved routine only. */
  query(
    sql:string,
    parameters:readonly [string,string],
  ):Promise<{rows:readonly unknown[]}>
}

/**
 * Bind to the pinned, isolated SQL fixture on the existing CI PostgreSQL
 * service. For a real deployment, a separately audited production routine,
 * authenticated connection, and independently read generation are REQUIRED.
 */
export function createIsolatedPostgresGenerationCheckpointV1(
  authenticated_client:AuthenticatedParameterizedPostgresV1,
):AuthenticatedAtomicGenerationCheckpointV1 {
  if(!authenticated_client||typeof authenticated_client.query!=='function') {
    throw new TypeError('trusted parameterized PostgreSQL client required')
  }
  return Object.freeze({
    async observe_and_advance(policy_id:string, observed_generation:string) {
      if(typeof policy_id!=='string'||!POLICY_ID.test(policy_id)
        ||typeof observed_generation!=='string'||!DEC.test(observed_generation)) {
        return {outcome:'UNAVAILABLE' as const}
      }
      try {
        const response=await authenticated_client.query(
          FUNCTION_SQL,[policy_id,observed_generation],
        )
        if(!response||!Array.isArray(response.rows)
          ||response.rows.length!==1
          ||response.rows[0]===null||typeof response.rows[0]!=='object'
          ||Array.isArray(response.rows[0])) {
          return {outcome:'UNAVAILABLE' as const}
        }
        const row=response.rows[0] as Record<string,unknown>
        if(row.outcome==='ACCEPTED'
          && typeof row.persisted_generation==='string'
          && DEC.test(row.persisted_generation)
          && row.persisted_generation===observed_generation) {
          return {
            outcome:'ACCEPTED' as const,
            persisted_generation:row.persisted_generation,
          }
        }
        if((row.outcome==='ROLLBACK'||row.outcome==='UNAVAILABLE')
          && (row.persisted_generation===null
            ||row.persisted_generation===undefined)) {
          return {outcome:row.outcome}
        }
        return {outcome:'UNAVAILABLE' as const}
      } catch {
        return {outcome:'UNAVAILABLE' as const}
      }
    },
  })
}
