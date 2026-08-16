import { createCockroachStore } from './cockroach-store.mjs';
import { runMemorySentinel } from './openai-agent.mjs';
import { createLambdaHandler } from './lambda-core.mjs';

let storePromise;

async function getStore() {
  if (!storePromise) storePromise = createCockroachStore();
  return storePromise;
}

export const handler = createLambdaHandler({
  createStore: getStore,
  runAgent: runMemorySentinel,
});
