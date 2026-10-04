import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

import { afterEach, describe, expect, test } from 'vitest';

import {
  FileProviderClaimLeaseStoreV1,
  ProviderClaimLeaseError,
} from '../../src/collective/provider-claim-lease';

interface VectorCorpusV1 {
  schema_version: '1.0.0';
  corpus_kind: 'UCI2_PROVIDER_CLAIM_STATE_VECTORS_V1';
  valid_states: Array<{ id: string; state: unknown }>;
  invalid_states: Array<{ id: string; expected_error: string; state: unknown }>;
}

const corpusPath = path.resolve(
  process.cwd(),
  '..',
  'test-vectors',
  'collective-intelligence',
  'uci-2-provider-claim-v1.json',
);

const roots: string[] = [];
const loadCorpus = (): VectorCorpusV1 =>
  JSON.parse(readFileSync(corpusPath, 'utf8')) as VectorCorpusV1;

const withStateFile = (state: unknown): string => {
  const root = mkdtempSync(path.join(tmpdir(), 'aegis-uci2-vector-'));
  roots.push(root);
  const statePath = path.join(root, 'claims.json');
  writeFileSync(statePath, JSON.stringify(state, null, 2), 'utf8');
  return statePath;
};

afterEach(() => {
  while (roots.length > 0) rmSync(roots.pop()!, { recursive: true, force: true });
});

describe('UCI-2 persisted provider-claim vectors', () => {
  test('publishes the exact nominal corpus', () => {
    const corpus = loadCorpus();
    expect(corpus.schema_version).toBe('1.0.0');
    expect(corpus.corpus_kind).toBe('UCI2_PROVIDER_CLAIM_STATE_VECTORS_V1');
    expect(corpus.valid_states.length).toBeGreaterThanOrEqual(2);
    expect(corpus.invalid_states.length).toBeGreaterThanOrEqual(6);
  });

  test('accepts every canonical valid persisted state without rewriting bytes', () => {
    for (const vector of loadCorpus().valid_states) {
      const statePath = withStateFile(vector.state);
      const before = readFileSync(statePath, 'utf8');
      expect(() => new FileProviderClaimLeaseStoreV1(statePath), vector.id).not.toThrow();
      expect(readFileSync(statePath, 'utf8'), vector.id).toBe(before);
    }
  });

  test('fails closed on every canonical persisted-state falsifier', () => {
    for (const vector of loadCorpus().invalid_states) {
      const statePath = withStateFile(vector.state);
      try {
        new FileProviderClaimLeaseStoreV1(statePath);
        throw new Error(`VECTOR_UNEXPECTEDLY_ACCEPTED:${vector.id}`);
      } catch (error) {
        expect(error, vector.id).toBeInstanceOf(ProviderClaimLeaseError);
        expect((error as Error).message, vector.id).toBe(vector.expected_error);
      }
    }
  });

  test('replays the corpus with the same verdict sequence', () => {
    const run = (): string[] => {
      const verdicts: string[] = [];
      const corpus = loadCorpus();
      for (const vector of corpus.valid_states) {
        const statePath = withStateFile(vector.state);
        new FileProviderClaimLeaseStoreV1(statePath);
        verdicts.push(`${vector.id}:PASS`);
      }
      for (const vector of corpus.invalid_states) {
        const statePath = withStateFile(vector.state);
        try {
          new FileProviderClaimLeaseStoreV1(statePath);
          verdicts.push(`${vector.id}:UNEXPECTED_PASS`);
        } catch (error) {
          verdicts.push(`${vector.id}:${(error as Error).message}`);
        }
      }
      return verdicts;
    };

    expect(run()).toEqual(run());
  });
});
