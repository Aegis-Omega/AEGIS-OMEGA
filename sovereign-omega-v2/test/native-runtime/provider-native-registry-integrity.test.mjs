import test, {after} from 'node:test';
import assert from 'node:assert/strict';
import {loadRepositoryTypescript} from './load-repository-ts.mjs';
const loaded = await loadRepositoryTypescript([
  'sovereignty/provider-native-agents.ts', 'sovereignty/provider-mesh.ts', 'core/hashing.ts',
]);
after(loaded.cleanup);
const {buildProviderNativeAgentRegistryV1: build, selectProviderNativeAgentV1: select} = loaded.modules['sovereignty/provider-native-agents.ts'];
const {buildProviderMeshSnapshotV1: snapshot} = loaded.modules['sovereignty/provider-mesh.ts'];
const {hashValue} = loaded.modules['core/hashing.ts'];
const descriptors = ['openai', 'anthropic', 'google-cloud'].map(provider_id => ({
  provider_id, schema_version: '1.0.0', planes: ['INTELLIGENCE'],
  declared_capabilities: ['AGENT_EXECUTION', 'MODEL_INFERENCE'], authority_effect: 'NONE',
}));
const request = {required_capabilities: ['AGENT_EXECUTION', 'MODEL_INFERENCE'],
  allowed_providers: ['openai'], current_generation: '10', max_observation_age_generations: '1'};
async function fixture() {
  return {registry: await build(descriptors), snapshot: await snapshot(descriptors, descriptors.map((d, i) => ({
    schema_version: '1.0.0', provider_id: d.provider_id, state: 'OBSERVED_AVAILABLE',
    observed_capabilities: ['AGENT_EXECUTION', 'MODEL_INFERENCE'], observation_generation: '10',
    evidence_hash: String(i + 1).repeat(64), authority_effect: 'NONE',
  })))};
}
test('real registry and selector preserve the canonical agent identity', async () => {
  const f = await fixture(); const out = await select(f.snapshot, f.registry, request);
  assert.equal(out.outcome, 'SELECTED'); assert.equal(out.agent_id, 'provider-agent:openai');
  const {receipt_root, ...body} = out;
  assert.equal(receipt_root, await hashValue({domain: 'AEGIS_PROVIDER_NATIVE_AGENT_SELECTION_RECEIPT_V1', receipt: body}));
});
for (const [field, value] of [
  ['agent_id', 'provider-agent:forged'], ['transport', 'PROVIDER_NATIVE_TOOL_SURFACE'],
  ['declared_capabilities', ['AGENT_EXECUTION']], ['write_authority', 'GRANTED'],
  ['merge_authority', 'GRANTED'], ['deploy_authority', 'GRANTED'], ['financial_authority', 'GRANTED'],
  ['authority_effect', 'GRANT'], ['schema_version', '9.0.0'],
]) {
  test(`rejects modified agent ${field} despite unchanged registry root`, async () => {
    const f = await fixture(); f.registry.agents.find(a => a.provider_id === 'openai')[field] = value;
    await assert.rejects(select(f.snapshot, f.registry, request), /registry.*verification failed/);
  });
}
test('rejects a duplicate agent with a copied valid registry root', async () => {
  const f = await fixture(); f.registry.agents.push({...f.registry.agents[0]});
  await assert.rejects(select(f.snapshot, f.registry, request), /registry.*verification failed/);
});
test('rejects extra unknown agent carrying the unchanged registry root', async () => {
  const f = await fixture(); f.registry.agents.push({...f.registry.agents[0], provider_id:'unknown-provider'});
  await assert.rejects(select(f.snapshot, f.registry, request), /registry.*verification failed/);
});
test('rejects a tampered payload even when its attacker recomputes the root', async () => {
  const f = await fixture(); f.registry.agents[0].write_authority = 'GRANTED';
  const {registry_root, ...payload} = f.registry;
  f.registry.registry_root = await hashValue({domain:'AEGIS_PROVIDER_NATIVE_AGENT_REGISTRY_V1', ...payload});
  await assert.rejects(select(f.snapshot, f.registry, request), /registry.*verification failed/);
});
test('registry identity is captured before the first asynchronous hash', async () => {
  const f = await fixture(); const pending = select(f.snapshot, f.registry, request);
  f.registry.agents.find(a => a.provider_id === 'openai').agent_id = 'provider-agent:changed-during-await';
  const out = await pending;
  assert.equal(out.agent_id, 'provider-agent:openai');
});
test('request allow-list is captured before asynchronous validation', async () => {
  const f = await fixture(); const input = structuredClone(request);
  const pending = select(f.snapshot, f.registry, input); input.allowed_providers[0] = 'anthropic';
  assert.equal((await pending).provider_id, 'openai');
});
test('valid subset registry remains selectable', async () => {
  const f = await fixture(); f.registry = await build(descriptors.filter(d => d.provider_id === 'openai'));
  assert.equal((await select(f.snapshot, f.registry, request)).agent_id, 'provider-agent:openai');
});
test('stale evidence is denied by actual mesh, not a fake conductor', async () => {
  const f = await fixture();
  const out = await select(f.snapshot, f.registry, {...request, current_generation:'20'});
  assert.equal(out.outcome, 'DENIED'); assert.equal(out.agent_id, null);
});
