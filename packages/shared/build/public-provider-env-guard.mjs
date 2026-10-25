// Fail closed on secret-bearing VITE_* variables before Vite embeds them in JS.
export const BLOCKED_PUBLIC_PROVIDER_KEYS = Object.freeze([
  'VITE_DASHSCOPE_API_KEY',
  'VITE_CLAUDE_API_KEY',
  'VITE_ANTHROPIC_API_KEY',
  'VITE_OPENAI_API_KEY',
  'VITE_AZURE_OPENAI_API_KEY',
  'VITE_NEBIUS_API_KEY',
])

export function assertNoPublicProviderKeys(env) {
  for (const key of BLOCKED_PUBLIC_PROVIDER_KEYS) {
    if (typeof env?.[key] === 'string' && env[key].trim() !== '') {
      // Never print the value: provider keys are bearer credentials.
      throw new Error(`Refusing public Vite build: ${key} must be server-side only`)
    }
  }
}
