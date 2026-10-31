/**
 * Single-call, read-only AWS account -> provider-mesh planning pipeline.
 * It never invokes inference, reserves quota, or emits execution authority.
 */
import { collectAwsResourceReadsV1, type AwsReadCallV1 } from './aws-readonly-collector.js'
import { observeConnectedResourcesV1 } from './connected-resource-intake.js'
import { observeAwsAccountForProviderMeshV1 } from './provider-adapters/aws.js'
import {
  DECLARED_PROVIDER_CATALOG_V1, buildProviderMeshSnapshotV1, selectProviderV1,
  type ProviderCapabilityV1,
} from './provider-mesh.js'

export interface AwsPlanningRequestV1 {
  /** Caller-assigned monotonic observation generation, not wall-clock freshness. */
  observation_generation: string
  region: string
  required_capabilities: readonly ProviderCapabilityV1[]
  /** Additional metadata-only listing operations. Default false. */
  include_service_discovery?: boolean
}

/** Planning receipt only. No AWS cloud action or spending is authorized. */
export async function inspectAwsProviderForPlanningV1(
  call: AwsReadCallV1,
  request: AwsPlanningRequestV1,
) {
  if (!request || typeof request.observation_generation !== 'string' || !/^(0|[1-9][0-9]*)$/.test(request.observation_generation)) {
    throw new TypeError('observation_generation must be canonical unsigned decimal')
  }
  if (!Array.isArray(request.required_capabilities) || request.required_capabilities.length === 0) {
    throw new TypeError('required_capabilities must be nonempty')
  }
  const declaredAws = DECLARED_PROVIDER_CATALOG_V1.find(item => item.provider_id === 'aws')
  if (!declaredAws) throw new Error('AWS provider descriptor missing')
  const caps = request.required_capabilities
  const allowed = new Set(declaredAws.declared_capabilities)
  if (new Set(caps).size !== caps.length || caps.some(cap => !allowed.has(cap))) {
    throw new TypeError('required_capabilities must be unique and declared for AWS')
  }
  // Deliberately no Cost Explorer or operator-reported balance in this path.
  const aws = await collectAwsResourceReadsV1(call, {
    region: request.region,
    include_service_discovery: request.include_service_discovery === true,
  })
  const inventory = await observeConnectedResourcesV1({
    observation_generation: request.observation_generation,
    cloudflare: {
      ai_gateway_credit_balance: null,
      ai_gateway_topup_config: null,
      worker_account_settings: null,
      worker_scripts: null,
    },
    hugging_face: { account_plan: 'UNKNOWN', jobs_total: null },
    aws,
  })
  const awsObservation = await observeAwsAccountForProviderMeshV1(inventory)
  const snapshot = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [awsObservation])
  const selection = await selectProviderV1(snapshot, {
    required_capabilities: request.required_capabilities,
    allowed_providers: ['aws'],
    current_generation: request.observation_generation,
    max_observation_age_generations: '0',
  })
  // Defensive tripwire if a future selector starts promoting account-only reads.
  if (awsObservation.observed_capabilities.length !== 0 ||
      awsObservation.state === 'OBSERVED_AVAILABLE' ||
      selection.outcome !== 'DENIED' || selection.provider_id !== null) {
    throw new Error('AWS account-only observation must never authorize execution')
  }
  return {
    schema: 'AEGIS_AWS_PLANNING_PIPELINE_V1' as const,
    inventory,
    snapshot,
    selection,
    disposition: 'HOLD' as const,
    authority_effect: 'NONE' as const,
  }
}
