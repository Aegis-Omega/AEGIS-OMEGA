export const FORMAL_SOURCE_AUDIT_AUTHORITY = 'SOURCE_AUDIT_ONLY' as const;

export type FormalSourceKindV1 = 'COQ' | 'LEAN';

export interface FormalSourceAuditV1 {
  readonly source_kind: FormalSourceKindV1;
  readonly strict_eligible: boolean;
  readonly forbidden_tokens: readonly string[];
  readonly authority: typeof FORMAL_SOURCE_AUDIT_AUTHORITY;
}

function stripCoqComments(source: string): string {
  let out = '';
  let depth = 0;
  for (let index = 0; index < source.length; index += 1) {
    const pair = source.slice(index, index + 2);
    if (pair === '(*') {
      depth += 1;
      index += 1;
      continue;
    }
    if (pair === '*)' && depth > 0) {
      depth -= 1;
      index += 1;
      continue;
    }
    if (depth === 0) out += source[index];
  }
  return out;
}

function stripLeanComments(source: string): string {
  let out = '';
  let blockDepth = 0;
  let lineComment = false;
  for (let index = 0; index < source.length; index += 1) {
    const pair = source.slice(index, index + 2);
    if (lineComment) {
      if (source[index] === '\n') {
        lineComment = false;
        out += '\n';
      }
      continue;
    }
    if (blockDepth === 0 && pair === '--') {
      lineComment = true;
      index += 1;
      continue;
    }
    if (pair === '/-') {
      blockDepth += 1;
      index += 1;
      continue;
    }
    if (pair === '-/' && blockDepth > 0) {
      blockDepth -= 1;
      index += 1;
      continue;
    }
    if (blockDepth === 0) out += source[index];
  }
  return out;
}

function uniqueInOrder(tokens: string[]): string[] {
  const seen = new Set<string>();
  return tokens.filter((token) => {
    if (seen.has(token)) return false;
    seen.add(token);
    return true;
  });
}

export function auditFormalSource(kind: FormalSourceKindV1, source: string): FormalSourceAuditV1 {
  if (typeof source !== 'string' || source.length === 0) throw new Error('FORMAL_SOURCE_EMPTY');

  const stripped = kind === 'COQ' ? stripCoqComments(source) : stripLeanComments(source);
  const forbidden: string[] = [];

  if (kind === 'COQ') {
    if (/\bAxiom\b/.test(stripped)) forbidden.push('Axiom');
    if (/\bParameters?\b/.test(stripped)) forbidden.push('Parameter');
    if (/\bAdmitted\b/.test(stripped)) forbidden.push('Admitted');
    if (/\badmit\b/.test(stripped)) forbidden.push('admit');
  } else if (kind === 'LEAN') {
    if (/\bsorry\b/.test(stripped)) forbidden.push('sorry');
    if (/\badmit\b/.test(stripped)) forbidden.push('admit');
  } else {
    const exhaustive: never = kind;
    throw new Error(`FORMAL_SOURCE_KIND_INVALID:${String(exhaustive)}`);
  }

  const forbiddenTokens = Object.freeze(uniqueInOrder(forbidden));
  return Object.freeze({
    source_kind: kind,
    strict_eligible: forbiddenTokens.length === 0,
    forbidden_tokens: forbiddenTokens,
    authority: FORMAL_SOURCE_AUDIT_AUTHORITY,
  });
}
