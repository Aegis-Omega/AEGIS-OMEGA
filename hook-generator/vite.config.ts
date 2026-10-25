import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'url'
import { resolve } from 'path'

const __dirname = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    // @shared ships its own react copy for type-checking; dedupe so the bundle
    // contains a single React instance (two copies => null hooks dispatcher =>
    // "Cannot read properties of null (reading 'useState')" white screen).
    dedupe: ['react', 'react-dom'],
    alias: {
      '@shared': resolve(__dirname, '../packages/shared'),
    },
  },
})
