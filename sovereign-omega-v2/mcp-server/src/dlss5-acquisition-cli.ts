#!/usr/bin/env node
import { readFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'

import { acquireDlss5Evidence } from './dlss5-acquisition.js'

const NVIDIA_SMI_ARGS = [
  '--query-gpu=name,driver_version,pci.bus_id',
  '--format=csv,noheader,nounits',
]

const result = acquireDlss5Evidence(
  {
    candidate_sha: process.env['AEGIS_CANDIDATE_SHA'] ?? '',
    capability_receipt_digest: process.env['AEGIS_DLSS5_CAPABILITY_RECEIPT_DIGEST'] ?? '',
    streamline_version: process.env['AEGIS_DLSS5_STREAMLINE_VERSION'] ?? '',
    streamline_plugin_path: process.env['AEGIS_DLSS5_STREAMLINE_PLUGIN_PATH'] ?? '',
    gpu_pci_bus_id: process.env['AEGIS_DLSS5_GPU_PCI_BUS_ID'],
  },
  {
    queryGpu: () => {
      const probe = spawnSync('nvidia-smi', NVIDIA_SMI_ARGS, {
        encoding: 'utf8',
        timeout: 5_000,
        windowsHide: true,
      })
      return {
        ok: probe.status === 0 && probe.error === undefined,
        stdout: probe.stdout ?? '',
        error: probe.error?.message ?? (probe.status === 0 ? undefined : `exit:${probe.status ?? 'unknown'}`),
      }
    },
    readPlugin: (path) => {
      try { return readFileSync(path) }
      catch { return null }
    },
    now: () => new Date().toISOString(),
  },
)

console.log(JSON.stringify(result, null, 2))
process.exitCode = result.status === 'EVIDENCE_CAPTURED' ? 0 : 2
