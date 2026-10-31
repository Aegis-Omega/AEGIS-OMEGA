/** Atomic Nebius attempt reservation; fail closed on absent/invalid RPC replies. */
export async function reserveNebiusAttempt(
  reserve: () => Promise<{ data: unknown; error: unknown }>,
): Promise<boolean> {
  try {
    const { data, error } = await reserve()
    return error == null && data === true
  } catch {
    return false
  }
}
