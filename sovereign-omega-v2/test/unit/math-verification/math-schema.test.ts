import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, test } from 'vitest';

const schemaRoot = path.resolve(process.cwd(), '..', 'schemas', 'math-verification');
const load = (name: string): Record<string, any> => JSON.parse(readFileSync(path.join(schemaRoot, name), 'utf8'));

function closedObjects(value: unknown, at = '$'): string[] {
  if (!value || typeof value !== 'object') return [];
  const obj = value as Record<string, unknown>;
  const errors: string[] = [];
  if (obj.type === 'object' && obj.additionalProperties !== false) errors.push(`${at}:open`);
  for (const [key, child] of Object.entries(obj)) errors.push(...closedObjects(child, `${at}.${key}`));
  return errors;
}

const cases = [
  ['math-claim-envelope-v1.schema.json', 'claim_kind', 'MATH_CLAIM_ENVELOPE_V1', 'NON_AUTHORITATIVE_MATH_CLAIM'],
  ['formalization-binding-v1.schema.json', 'binding_kind', 'FORMALIZATION_BINDING_V1', 'FORMALIZATION_BINDING_ONLY'],
  ['kernel-verification-result-v1.schema.json', 'result_kind', 'KERNEL_VERIFICATION_RESULT_V1', 'KERNEL_RESULT_ONLY'],
  ['math-verification-receipt-v1.schema.json', 'receipt_kind', 'MATH_VERIFICATION_RECEIPT_V1', 'FORMAL_MATH_EVIDENCE_ONLY'],
] as const;

describe('MATH_DISPROVAL_GATE_V1 schemas', () => {
  test.each(cases)('%s is a closed nominal Draft 2020-12 contract', (file, kindField, kind, authority) => {
    const schema = load(file);
    expect(schema.$schema).toBe('https://json-schema.org/draft/2020-12/schema');
    expect(schema.type).toBe('object');
    expect(schema.additionalProperties).toBe(false);
    expect(closedObjects(schema)).toEqual([]);
    expect(schema.properties[kindField].const).toBe(kind);
    expect(schema.properties.authority.const).toBe(authority);
  });

  test('kernel schema separates process failure from truth-producing artifacts', () => {
    const schema = load('kernel-verification-result-v1.schema.json');
    expect(new Set(schema.properties.process_status.enum)).toEqual(new Set(['VERIFIED', 'REJECTED', 'TIMEOUT', 'ERROR']));
    expect(new Set(schema.properties.attempt_kind.enum)).toEqual(new Set(['PROVE', 'DISPROVE_NEGATION', 'DISPROVE_COUNTEREXAMPLE']));
    expect(new Set(schema.properties.kernel_family.enum)).toEqual(new Set(['COQ', 'LEAN']));
  });

  test('receipt schema has truth and verification diversity as separate axes and no execution authority surface', () => {
    const schema = load('math-verification-receipt-v1.schema.json');
    expect(new Set(schema.properties.verdict.enum)).toEqual(new Set(['PROVED', 'DISPROVED', 'UNRESOLVED']));
    expect(new Set(schema.properties.verification_level.enum)).toEqual(new Set(['SINGLE_KERNEL', 'CROSS_KERNEL']));
    for (const forbidden of ['permit', 'execute', 'decision_receipt', 'execution_receipt', 'effect_receipt', 'admission']) {
      expect(schema.properties[forbidden]).toBeUndefined();
    }
  });
});
