import OpenAI from 'openai';
import { Agent, run, tool } from '@openai/agents';
import { z } from 'zod';

import { createAgentTools } from './agent-tools.mjs';
import { MEMORY_SENTINEL_INSTRUCTIONS } from './agent-contract.mjs';
import { summarizeRunEvidence } from './run-evidence.mjs';

const DEFAULT_AGENT_MODEL = 'gpt-5.6-luna';
const DEFAULT_EMBEDDING_MODEL = 'text-embedding-3-small';

function createEmbedder(openai) {
  return async (text) => {
    const response = await openai.embeddings.create({
      model: process.env.OPENAI_EMBEDDING_MODEL ?? DEFAULT_EMBEDDING_MODEL,
      input: text,
    });
    const embedding = response.data[0]?.embedding;
    if (!embedding) throw new Error('embedding response missing vector');
    return embedding;
  };
}

export function createMemorySentinelAgent({ store, openai = new OpenAI() }) {
  const domain = createAgentTools({ store, embed: createEmbedder(openai) });

  const observeCollectiveState = tool({
    name: 'observe_collective_state',
    description: 'Read one persisted MCM node state and derive observation-only verification demand. This tool never grants authority.',
    parameters: z.object({ nodeId: z.string().min(1) }),
    execute: async ({ nodeId }) => domain.observeCollectiveState({ nodeId }),
  });

  const searchEvidence = tool({
    name: 'search_evidence',
    description: 'Embed a query and retrieve semantically similar evidence from CockroachDB VECTOR memory. Retrieval is evidence only, not admission.',
    parameters: z.object({
      query: z.string().min(1),
      epistemicTier: z.string().min(1).default('T2'),
      limit: z.number().int().min(1).max(20).default(5),
    }),
    execute: async ({ query, epistemicTier, limit }) => domain.searchEvidence({ query, epistemicTier, limit }),
  });

  const evaluateActionMemory = tool({
    name: 'evaluate_action_memory',
    description: 'Deterministically compare an observed action/state/policy tuple with the admitted CockroachDB memory tuple. DENY is binding for this agent.',
    parameters: z.object({
      nodeId: z.string().min(1),
      requestId: z.string().min(1),
      actionDigest: z.string().min(1),
      observedStateDigest: z.string().min(1),
      observedPolicyDigest: z.string().min(1),
      observedAuthorityEpoch: z.number().int().nonnegative(),
      priorReceiptActionDigest: z.string().nullable().optional(),
    }),
    execute: async (input) => domain.evaluateAction(input),
  });

  return new Agent({
    name: 'AEGIS Memory Sentinel',
    model: process.env.OPENAI_MODEL ?? DEFAULT_AGENT_MODEL,
    instructions: MEMORY_SENTINEL_INSTRUCTIONS,
    tools: [observeCollectiveState, searchEvidence, evaluateActionMemory],
  });
}

export async function runMemorySentinel({ prompt, store, openai }) {
  if (typeof prompt !== 'string' || prompt.trim().length === 0) throw new TypeError('prompt required');
  const agent = createMemorySentinelAgent({ store, openai });
  const result = await run(agent, prompt);
  return summarizeRunEvidence(result);
}
