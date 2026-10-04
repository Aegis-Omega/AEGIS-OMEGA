import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, test } from 'vitest';

import { validateCollectiveWorkGraph } from '../../src/collective/validate';

type VectorCase = {
  id: string;
  expected_ok: boolean;
  expected_error_prefix?: string;
  payload: unknown;
};

type VectorCorpus = {
  schema_version: '1.0.0';
  vector_kind: 'UCI_1_COLLECTIVE_WORK_VECTORS_V1';
  cases: VectorCase[];
};

const vectorPath = path.resolve(
  process.cwd(),
  '..',
  'test-vectors',
  'collective-intelligence',
  'uci-1-v1.json',
);

const corpus = JSON.parse(readFileSync(vectorPath, 'utf8')) as VectorCorpus;

describe('UCI-1 collective work canonical vectors', () => {
  test('uses the nominal vector corpus discriminator', () => {
    expect(corpus.schema_version).toBe('1.0.0');
    expect(corpus.vector_kind).toBe('UCI_1_COLLECTIVE_WORK_VECTORS_V1');
  });

  for (const vector of [...corpus.cases].sort((a, b) => a.id.localeCompare(b.id))) {
    test(vector.id, () => {
      const result = validateCollectiveWorkGraph(vector.payload);
      expect(result.ok).toBe(vector.expected_ok);
      if (!vector.expected_ok) {
        expect(result.ok).toBe(false);
        if (!result.ok && vector.expected_error_prefix) {
          expect(result.errors.some((error) => error.startsWith(vector.expected_error_prefix!))).toBe(true);
        }
      }
    });
  }
});
