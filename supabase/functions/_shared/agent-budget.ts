/** TAR-21 atomic replay+quota admission. No in-memory counters or client-controlled limits. */
export type AdmissionKind = 'slack' | 'operator'
export type BudgetRpcClient = {
  rpc: (name: string, args: { p_kind: AdmissionKind; p_actor_id: string; p_request_key: string }) =>
    PromiseLike<{ data: unknown; error: unknown }>
}

export async function reserveAgentExecution(
  client: BudgetRpcClient, kind: AdmissionKind, actorId: string, requestKey: string,
): Promise<'reserved' | 'denied' | 'unavailable'> {
  if (!['slack', 'operator'].includes(kind)
    || !/^[A-Za-z0-9:._-]{1,160}$/.test(actorId)
    || !/^[A-Za-z0-9:._-]{8,180}$/.test(requestKey)) return 'denied'
  try {
    const { data, error } = await client.rpc('aegis_agent_reserve_budget', {
      p_kind: kind, p_actor_id: actorId, p_request_key: requestKey,
    })
    return error ? 'unavailable' : data === true ? 'reserved' : data === false ? 'denied' : 'unavailable'
  } catch { return 'unavailable' }
}
