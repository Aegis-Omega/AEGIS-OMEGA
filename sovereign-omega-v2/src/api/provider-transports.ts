import Anthropic from '@anthropic-ai/sdk'
import type { Deployment, InferenceTransport, ProviderResult } from './inference-gateway.js'

/** Anthropic credentials remain server-side in the registered transport. */
export class AnthropicTransport implements InferenceTransport {
  readonly provider = 'anthropic' as const
  constructor(private readonly client: Pick<Anthropic, 'messages'>) {}
  async invoke(payload: unknown, deployment: Deployment): Promise<ProviderResult<unknown>> {
    const response = await this.client.messages.create({ ...(payload as Anthropic.MessageCreateParamsNonStreaming), model: deployment.model })
    return { value: response, inputTokens: response.usage.input_tokens, outputTokens: response.usage.output_tokens }
  }
}

export interface AzureCredentialSource { accessToken(): Promise<string> }
/** Azure transport accepts only server-side managed-identity/Key Vault token sources, never browser API keys. */
export class MicrosoftFoundryTransport implements InferenceTransport {
  readonly provider = 'microsoft-foundry' as const
  constructor(private readonly endpoint: string, private readonly credentials: AzureCredentialSource, private readonly fetcher: typeof fetch = fetch) {}
  async invoke(payload: unknown, deployment: Deployment): Promise<ProviderResult<unknown>> {
    const token = await this.credentials.accessToken()
    const response = await this.fetcher(`${this.endpoint}/openai/deployments/${encodeURIComponent(deployment.name)}/chat/completions?api-version=2024-10-21`, { method: 'POST', headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' }, body: JSON.stringify(payload) })
    if (!response.ok) throw new Error(`Foundry returned ${response.status}`)
    const body = await response.json() as { usage?: { prompt_tokens?: number; completion_tokens?: number } }
    return { value: body, inputTokens: body.usage?.prompt_tokens ?? 0, outputTokens: body.usage?.completion_tokens ?? 0 }
  }
}

/** Vertex is injected as a server-side transport so service-account credentials never cross the gateway boundary. */
export class VertexAiTransport implements InferenceTransport {
  readonly provider = 'vertex-ai' as const
  constructor(private readonly invokeVertex: (deployment: Deployment, payload: unknown) => Promise<ProviderResult<unknown>>) {}
  invoke(payload: unknown, deployment: Deployment): Promise<ProviderResult<unknown>> { return this.invokeVertex(deployment, payload) }
}
