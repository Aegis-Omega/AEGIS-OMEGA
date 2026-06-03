import { App } from './app.js'
import { showNoWebGPU } from './ui/layout.js'

const app = new App()

app.init()
  .then(() => { app.start() })
  .catch((err: unknown) => {
    console.error('AEGIS WebGPU init failed:', err)
    showNoWebGPU()
  })
