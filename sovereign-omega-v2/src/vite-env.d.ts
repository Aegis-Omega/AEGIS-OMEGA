// Augments ImportMeta so import.meta.env is typed for packages/shared files
// compiled under this tsconfig (tsc --noEmit, no Vite bundler involved).
interface ImportMetaEnv {
  readonly VITE_DASHSCOPE_API_KEY?: string
  readonly VITE_DASHSCOPE_MODEL?: string
  readonly VITE_DASHSCOPE_BASE_URL?: string
  readonly VITE_OLLAMA_BASE_URL?: string
  readonly VITE_OLLAMA_MODEL?: string
  readonly VITE_CLAUDE_API_KEY?: string
  readonly VITE_CLAUDE_MODEL?: string
  readonly VITE_BRIDGE_URL?: string
  readonly [key: string]: string | undefined
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
