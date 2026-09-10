const VECTOR_DIMENSIONS = 1536;

export function toVectorLiteral(embedding) {
  if (!Array.isArray(embedding) || embedding.length !== VECTOR_DIMENSIONS) {
    throw new RangeError(`embedding must contain exactly ${VECTOR_DIMENSIONS} dimensions`);
  }
  if (!embedding.every(Number.isFinite)) {
    throw new TypeError('embedding dimensions must be finite numbers');
  }
  return `[${embedding.join(',')}]`;
}

export class CockroachMemoryStore {
  constructor(client) {
    if (!client || typeof client.query !== 'function') {
      throw new TypeError('query-capable client required');
    }
    this.client = client;
  }

  async getNodeState(nodeId) {
    if (typeof nodeId !== 'string' || nodeId.length === 0) {
      throw new TypeError('nodeId required');
    }
    const result = await this.client.query(
      `SELECT node_id, sequence, confidence_bps, evidence_freshness_bps, load_bps,
              reliability_bps, contradiction_count, observed_authority_envelope,
              state_digest, policy_digest, authority_epoch, previous_receipt_hash
         FROM mcm_node_state
        WHERE node_id = $1`,
      [nodeId],
    );
    return result.rows[0] ?? null;
  }

  async findEvidence({ epistemicTier, embedding, limit = 5 }) {
    if (typeof epistemicTier !== 'string' || epistemicTier.length === 0) {
      throw new TypeError('epistemicTier required');
    }
    if (!Number.isSafeInteger(limit) || limit < 1 || limit > 50) {
      throw new RangeError('limit must be integer 1..50');
    }
    const vector = toVectorLiteral(embedding);
    const result = await this.client.query(
      `SELECT memory_id, node_id, memory_kind, evidence_text, evidence_digest,
              source_ref, epistemic_tier, freshness_bps,
              embedding <-> $2::VECTOR AS distance
         FROM mcm_evidence_memory
        WHERE epistemic_tier = $1 AND embedding IS NOT NULL
        ORDER BY embedding <-> $2::VECTOR
        LIMIT $3`,
      [epistemicTier, vector, limit],
    );
    return result.rows;
  }
}

export async function createCockroachStore({ url = process.env.COCKROACH_URL } = {}) {
  if (!url) throw new Error('COCKROACH_URL is required');
  const { Pool } = await import('pg');
  const pool = new Pool({
    connectionString: url,
    max: 4,
    ssl: url.includes('sslmode=disable') ? false : undefined,
  });
  return new CockroachMemoryStore(pool);
}
