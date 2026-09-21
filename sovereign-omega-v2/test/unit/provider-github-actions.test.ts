import { describe, expect, it } from 'vitest'
import { observeGitHubActionsJobV1 } from '../../src/sovereignty/provider-adapters/github-actions.js'

describe('GitHub Actions provider adapter v1', () => {
  it('marks terminal pre-start runner failure as unavailable', async () => {
    const observed = await observeGitHubActionsJobV1({
      run_id: '35503159820',
      job_id: '106058400192',
      head_sha: '25f04db15bef28d7f34524671bc199357a6855e0',
      status: 'completed',
      conclusion: 'failure',
      runner_id: 0,
      runner_name: '',
      steps_count: 0,
    }, '20')

    expect(observed.state).toBe('OBSERVED_UNAVAILABLE')
    expect(observed.provider_id).toBe('github-actions')
    expect(observed.observed_capabilities).toEqual(['DURABLE_RUNNER', 'REPOSITORY_WORKFLOW'])
    expect(observed.authority_effect).toBe('NONE')
  })

  it('keeps provider available when a real runner executed steps but workload failed', async () => {
    const observed = await observeGitHubActionsJobV1({
      run_id: '42',
      job_id: '99',
      head_sha: 'a'.repeat(40),
      status: 'completed',
      conclusion: 'failure',
      runner_id: 17,
      runner_name: 'GitHub Actions 17',
      steps_count: 4,
    }, '20')

    expect(observed.state).toBe('OBSERVED_AVAILABLE')
  })

  it('marks a successful executed job as available', async () => {
    const observed = await observeGitHubActionsJobV1({
      run_id: '43',
      job_id: '100',
      head_sha: 'b'.repeat(40),
      status: 'completed',
      conclusion: 'success',
      runner_id: 18,
      runner_name: 'GitHub Actions 18',
      steps_count: 6,
    }, '20')

    expect(observed.state).toBe('OBSERVED_AVAILABLE')
  })

  it('does not promote queued or in-progress metadata', async () => {
    const observed = await observeGitHubActionsJobV1({
      run_id: '44',
      job_id: '101',
      head_sha: 'c'.repeat(40),
      status: 'queued',
      conclusion: null,
      runner_id: 0,
      runner_name: '',
      steps_count: 0,
    }, '20')

    expect(observed.state).toBe('UNKNOWN')
    expect(observed.observed_capabilities).toEqual([])
  })

  it('rejects contradictory zero-runner metadata', async () => {
    await expect(observeGitHubActionsJobV1({
      run_id: '45',
      job_id: '102',
      head_sha: 'd'.repeat(40),
      status: 'completed',
      conclusion: 'failure',
      runner_id: 0,
      runner_name: 'impossible-runner-name',
      steps_count: 0,
    }, '20')).rejects.toThrow('runner_name must be empty when runner_id is zero')
  })
})
