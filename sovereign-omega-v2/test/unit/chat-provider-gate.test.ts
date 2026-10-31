import { describe, expect, it } from 'vitest'
import { routeChatProviderV1 } from '../../../supabase/functions/_shared/chat-provider-gate.ts'

const enabled = { openai: true, nebius: true, azure: true }
const disabled = { openai: false, nebius: false, azure: false }

describe('AEGIS chat exact provider routing and no paid fallback', () => {
  it('defaults to DashScope only when provider is omitted', () => {
    expect(routeChatProviderV1(undefined,disabled)).toEqual({
      outcome:'SELECTED',provider:'dashscope',provider_id:'dashscope',
    })
  })
  it('preserves an explicitly enabled provider and exact provider identity', () => {
    for(const [provider,id] of [
      ['openai','openai'],['nebius','nebius-token-factory'],
      ['azure','azure-openai'],['dashscope','dashscope'],
    ]) expect(routeChatProviderV1(provider,enabled)).toEqual({
      outcome:'SELECTED',provider,provider_id:id,
    })
  })
  it('does not silently route disabled OpenAI to DashScope', () => {
    expect(routeChatProviderV1('openai',disabled)).toEqual({
      outcome:'DENIED',denial_code:'PROVIDER_DISABLED',provider_id:'openai',
    })
  })
  it('does not silently route disabled Azure to DashScope', () => {
    expect(routeChatProviderV1('azure',disabled)).toEqual({
      outcome:'DENIED',denial_code:'PROVIDER_DISABLED',provider_id:'azure-openai',
    })
  })
  it('does not silently route disabled Nebius to DashScope', () => {
    expect(routeChatProviderV1('nebius',disabled)).toEqual({
      outcome:'DENIED',denial_code:'PROVIDER_DISABLED',provider_id:'nebius-token-factory',
    })
  })
  it('rejects unknown strings instead of treating them as DashScope', () => {
    for(const invalid of ['unknown','','openai ','constructor','toString']) {
      expect(routeChatProviderV1(invalid,enabled)).toEqual({
        outcome:'DENIED',denial_code:'INVALID_PROVIDER',provider_id:null,
      })
    }
  })
  it('rejects non-string caller values', () => {
    for(const invalid of [null,0,{},[],false,['openai']]) {
      expect(routeChatProviderV1(invalid,enabled)).toEqual({
        outcome:'DENIED',denial_code:'INVALID_PROVIDER',provider_id:null,
      })
    }
  })
  it('validates flags independently and denies even when other providers are enabled', () => {
    expect(routeChatProviderV1('openai',{openai:false,nebius:true,azure:true}).outcome).toBe('DENIED')
    expect(routeChatProviderV1('azure',{openai:true,nebius:true,azure:false}).outcome).toBe('DENIED')
  })
})
