import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import { Pool } from 'pg';

const url = process.env.COCKROACH_URL;
if (!url) {
  console.error('COCKROACH_URL is required');
  process.exit(2);
}

const pool = new Pool({
  connectionString: url,
  max: 2,
  ssl: url.includes('sslmode=disable') ? false : undefined,
});

const vectorA = `[${Array.from({ length: 1536 }, (_, i) => (i === 0 ? 1 : 0)).join(',')}]`;
const vectorB = `[${Array.from({ length: 1536 }, (_, i) => (i === 0 ? 0.9 : i === 1 ? 0.1 : 0)).join(',')}]`;
const queryVector = vectorA;

const core = {
  skill_binding: {
    repository: 'cockroachlabs/cockroachdb-skills',
    commit: 'e14e86d23ce8ee2e7e40a34ce2944c2502b6eadd',
    skill: 'cockroachdb-sql',
    blob_sha: '2690e972a99fe632818f0fc1a434080bc7acd917',
  },
  checks: {},
};

const client = await pool.connect();
try {
  const version = await client.query('SELECT version() AS version');
  const engine = version.rows[0]?.version ?? '';
  if (!/CockroachDB/i.test(engine)) throw new Error(`unexpected database engine: ${engine}`);
  core.checks.engine = { status: 'PASS', version: engine };

  const schema = await fs.readFile(new URL('../db/schema.sql', import.meta.url), 'utf8');
  await client.query(schema);
  core.checks.schema_apply = { status: 'PASS' };

  const showCreate = await client.query('SHOW CREATE TABLE mcm_evidence_memory');
  core.checks.show_create = {
    status: 'PASS',
    rows: showCreate.rowCount,
  };

  await client.query(
    `UPSERT INTO mcm_node_state (
       node_id, sequence, confidence_bps, evidence_freshness_bps, load_bps,
       reliability_bps, contradiction_count, observed_authority_envelope,
       state_digest, policy_digest, authority_epoch, previous_receipt_hash
     ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)`,
    ['agent-7', 8, 6200, 4100, 8800, 7300, 2, 'D2', 'sha256:state-5', 'sha256:policy-3', 7, null],
  );

  await client.query(
    `UPSERT INTO mcm_evidence_memory (
       memory_id, node_id, memory_kind, evidence_text, evidence_digest,
       source_ref, epistemic_tier, freshness_bps, embedding
     ) VALUES
       ('00000000-0000-0000-0000-000000000001', $1, 'verification', 'stale-state verification evidence', 'sha256:evidence-a', 'demo:a', 'T2', 9000, $2::VECTOR),
       ('00000000-0000-0000-0000-000000000002', $1, 'observation', 'resource-pressure observation', 'sha256:evidence-b', 'demo:b', 'T2', 7000, $3::VECTOR)`,
    ['agent-7', vectorA, vectorB],
  );
  core.checks.seed = { status: 'PASS', evidence_rows: 2 };

  const explain = await client.query(
    `EXPLAIN SELECT memory_id, evidence_digest, embedding <-> $2::VECTOR AS distance
       FROM mcm_evidence_memory
      WHERE epistemic_tier = $1 AND embedding IS NOT NULL
      ORDER BY embedding <-> $2::VECTOR
      LIMIT 2`,
    ['T2', queryVector],
  );
  if (explain.rowCount < 1) throw new Error('EXPLAIN returned no plan rows');
  core.checks.explain = { status: 'PASS', plan_rows: explain.rowCount };

  const nearest = await client.query(
    `SELECT memory_id, evidence_digest, embedding <-> $2::VECTOR AS distance
       FROM mcm_evidence_memory
      WHERE epistemic_tier = $1 AND embedding IS NOT NULL
      ORDER BY embedding <-> $2::VECTOR
      LIMIT 2`,
    ['T2', queryVector],
  );
  if (nearest.rows[0]?.evidence_digest !== 'sha256:evidence-a') {
    throw new Error('vector nearest-neighbor result did not preserve expected top match');
  }
  core.checks.vector_query = {
    status: 'PASS',
    returned: nearest.rowCount,
    top_evidence_digest: nearest.rows[0].evidence_digest,
  };

  const deterministic = JSON.stringify(core);
  const receipt = {
    ...core,
    receipt_sha256: crypto.createHash('sha256').update(deterministic).digest('hex'),
    observed_at: new Date().toISOString(),
    status: 'PASS',
  };

  const outputPath = new URL('../evidence/cockroach-runtime-receipt.json', import.meta.url);
  await fs.mkdir(new URL('../evidence/', import.meta.url), { recursive: true });
  await fs.writeFile(outputPath, `${JSON.stringify(receipt, null, 2)}\n`);
  console.log(JSON.stringify(receipt, null, 2));
} finally {
  client.release();
  await pool.end();
}
