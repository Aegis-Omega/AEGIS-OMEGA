/** No implicit provider substitution. Routing metadata is NOT execution authority. */
export type ChatProviderV1 = 'dashscope' | 'openai' | 'nebius' | 'azure'
export type ChatProviderFlagsV1 = Readonly<{
  openai: boolean
  nebius: boolean
  azure: boolean
}>
export type ChatProviderRouteV1 =
  | { outcome: 'SELECTED'; provider: ChatProviderV1; provider_id: string }
  | { outcome: 'DENIED'; denial_code: 'INVALID_PROVIDER' | 'PROVIDER_DISABLED'; provider_id: string | null }

/** Pure dispatch gate. A selected route must still pass account, credential, budget and mesh checks. */
export function routeChatProviderV1(
  requestedProvider: unknown,
  flags: ChatProviderFlagsV1,
): ChatProviderRouteV1 {
  const provider = requestedProvider === undefined ? 'dashscope' : requestedProvider
  if (provider !== 'dashscope' && provider !== 'openai' && provider !== 'nebius' && provider !== 'azure') {
    return { outcome: 'DENIED', denial_code: 'INVALID_PROVIDER', provider_id: null }
  }
  const id = provider === 'azure' ? 'azure-openai' : provider === 'nebius' ? 'nebius-token-factory' : provider
  if ((provider === 'openai' && flags.openai !== true)
    || (provider === 'nebius' && flags.nebius !== true)
    || (provider === 'azure' && flags.azure !== true)) {
    return { outcome: 'DENIED', denial_code: 'PROVIDER_DISABLED', provider_id: id }
  }
  return { outcome: 'SELECTED', provider, provider_id: id }
}
