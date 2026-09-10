import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import { verifyDeployment } from '../src/deployment-verifier.mjs';

const baseUrl = process.env.MEMORY_SENTINEL_URL;
const token = process.env.DEMO_TOKEN;

if (!baseUrl) {
  console.error('MEMORY_SENTINEL_URL is required');
  process.exit(2);
}
if (!token) {
  console.error('DEMO_TOKEN is required');
  process.exit(2);
}

const deployment = await verifyDeployment({ baseUrl, token });
const core = {
  schema_version: 1,
  receipt_type: 'AEGIS_MEMORY_SENTINEL_AWS_RUNTIME_RECEIPT',
  deployment,
};
const digest = crypto.createHash('sha256').update(JSON.stringify(core)).digest('hex');
const receipt = {
  ...core,
  receipt_sha256: digest,
  observed_at: new Date().toISOString(),
};

await fs.mkdir(new URL('../evidence/', import.meta.url), { recursive: true });
await fs.writeFile(
  new URL('../evidence/aws-runtime-receipt.json', import.meta.url),
  `${JSON.stringify(receipt, null, 2)}\n`,
);
console.log(JSON.stringify(receipt, null, 2));
