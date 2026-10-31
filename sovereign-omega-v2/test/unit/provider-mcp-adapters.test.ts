import { describe, expect, it } from 'vitest'
import { observeTavilyMcpV1 } from '../../src/sovereignty/provider-adapters/tavily.js'
import { observeHuggingFaceJobsV1 } from '../../src/sovereignty/provider-adapters/hugging-face-jobs.js'

describe('MCP provider observation adapters v1', () => {
  it('maps a successful Tavily keyed request to observed web-research availability', async () => {
    const observed = await observeTavilyMcpV1({
      request_id: 'request-1',
      auth_mode: 'keyed',
      outcome: 'SUCCESS',
      result_count: 4,
    }, '20')

    expect(observed.provider_id).toBe('tavily')
    expect(observed.state).toBe('OBSERVED_AVAILABLE')
    expect(observed.observed_capabilities).toEqual(['WEB_RESEARCH'])
    expect(observed.authority_effect).toBe('NONE')
  })

  it('does not turn a Tavily generic failure into provider unavailability', async () => {
    const observed = await observeTavilyMcpV1({
      request_id: 'request-2',
      auth_mode: 'keyed',
      outcome: 'FAILURE',
      result_count: 0,
    }, '20')

    expect(observed.state).toBe('UNKNOWN')
    expect(observed.observed_capabilities).toEqual([])
  })

  it('maps Hugging Face Jobs payment denial to observed execution unavailability', async () => {
    const observed = await observeHuggingFaceJobsV1({
      operation: 'run',
      outcome: 'PAYMENT_REQUIRED',
      flavor: 'cpu-basic',
      job_id: null,
    }, '20')

    expect(observed.provider_id).toBe('hugging-face-jobs')
    expect(observed.state).toBe('OBSERVED_UNAVAILABLE')
    expect(observed.observed_capabilities).toEqual([
      'CONTAINER_RUNTIME',
      'DURABLE_RUNNER',
      'GPU_COMPUTE',
    ])
    expect(observed.authority_effect).toBe('NONE')
  })

  it('maps an accepted Hugging Face job to observed execution availability', async () => {
    const observed = await observeHuggingFaceJobsV1({
      operation: 'run',
      outcome: 'JOB_ACCEPTED',
      flavor: 'cpu-basic',
      job_id: 'job-1',
    }, '20')

    expect(observed.state).toBe('OBSERVED_AVAILABLE')
  })

  it('keeps a generic Hugging Face workload failure epistemically unknown', async () => {
    const observed = await observeHuggingFaceJobsV1({
      operation: 'run',
      outcome: 'GENERIC_FAILURE',
      flavor: 'cpu-basic',
      job_id: 'job-2',
    }, '20')

    expect(observed.state).toBe('UNKNOWN')
    expect(observed.observed_capabilities).toEqual([])
  })
})
