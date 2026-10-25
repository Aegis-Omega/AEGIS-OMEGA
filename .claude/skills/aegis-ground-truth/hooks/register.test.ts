import { test, expect } from 'claude-code/testing'
import { stackedBase } from './register'

test('stacked branch and PR bases are caught, main is allowed', () => {
  expect(stackedBase('git checkout -b fix/x research/foo-v1')).toBe('research/foo-v1')
  expect(stackedBase('git switch -c fix/x proof/rh-v13')).toBe('proof/rh-v13')
  expect(stackedBase('gh pr create --base feat/y --title t')).toBe('feat/y')
  expect(stackedBase('git checkout -b fix/x origin/main')).toBeUndefined()
  expect(stackedBase('git checkout -b fix/x')).toBeUndefined()
  expect(stackedBase('gh pr create --base main')).toBeUndefined()
  expect(stackedBase('git branch -D old')).toBeUndefined()
})
