import {
  FrontierInferenceGateway,
  type FrontierAuthorizer,
  type FrontierDeployment,
  type FrontierInferenceProvider,
  type FrontierMeter,
  type StreamLeaseVerifier,
  type WorkOrderVerifier,
} from './frontier-inference-gateway.js'
import {
  FrontierHttpInferenceTransport,
  FrontierManagedInferenceTransport,
  FrontierTransportError,
  type FrontierCredentialHeaderResolver,
  type FrontierFetch,
  type FrontierHttpProtocol,
  type FrontierManagedInvoker,
} from './frontier-provider-transports.js'

export type FrontierRuntimeConnection =
  | {
      readonly kind: 'http'
      readonly provider: FrontierInferenceProvider
      readonly protocol: FrontierHttpProtocol
      readonly baseUrl: string
      readonly authReference: string
    }
  | {
      readonly kind: 'managed'
      readonly provider: 'google-vertex' | 'microsoft-foundry' | 'aws-bedrock'
    }

export interface FrontierRuntimeConfig {
  readonly deployments: readonly FrontierDeployment[]
  readonly connections: readonly FrontierRuntimeConnection[]
}

export interface FrontierRuntimeDependencies {
  readonly authorizer: FrontierAuthorizer
  readonly meter: FrontierMeter
  readonly workOrderVerifier: WorkOrderVerifier
  readonly streamLeaseVerifier: StreamLeaseVerifier
  readonly credentialHeaders: FrontierCredentialHeaderResolver
  readonly fetcher?: FrontierFetch | undefined
  readonly managedInvokers: Partial<Record<FrontierInferenceProvider, FrontierManagedInvoker>>
}

export interface FrontierRuntime {
  readonly gateway: FrontierInferenceGateway
  readonly configuredProviders: readonly FrontierInferenceProvider[]
}

export class FrontierRuntimeError extends Error {
  constructor(
    readonly code:
      | 'DUPLICATE_PROVIDER'
      | 'DEPLOYMENT_MISSING'
      | 'HTTP_TRANSPORT_MISSING'
      | 'MANAGED_TRANSPORT_MISSING'
      | 'TRANSPORT_INVALID',
    message: string,
  ) {
    super(message)
    this.name = 'FrontierRuntimeError'
  }
}

export function buildFrontierRuntime(
  config: FrontierRuntimeConfig,
  dependencies: FrontierRuntimeDependencies,
): FrontierRuntime {
  const seen = new Set<FrontierInferenceProvider>()
  const transports = []

  for (const connection of config.connections) {
    if (seen.has(connection.provider)) {
      throw new FrontierRuntimeError('DUPLICATE_PROVIDER', `duplicate frontier connection: ${connection.provider}`)
    }
    seen.add(connection.provider)

    if (!config.deployments.some(deployment => deployment.provider === connection.provider)) {
      throw new FrontierRuntimeError('DEPLOYMENT_MISSING', `frontier provider has no admitted deployment: ${connection.provider}`)
    }

    try {
      if (connection.kind === 'http') {
        if (dependencies.fetcher === undefined) {
          throw new FrontierRuntimeError('HTTP_TRANSPORT_MISSING', 'HTTP frontier connection requires an injected fetch transport')
        }
        transports.push(new FrontierHttpInferenceTransport(
          {
            provider: connection.provider,
            protocol: connection.protocol,
            baseUrl: connection.baseUrl,
            authReference: connection.authReference,
          },
          dependencies.credentialHeaders,
          dependencies.fetcher,
        ))
      } else {
        const invoker = dependencies.managedInvokers[connection.provider]
        if (invoker === undefined) {
          throw new FrontierRuntimeError('MANAGED_TRANSPORT_MISSING', `managed frontier provider has no runtime invoker: ${connection.provider}`)
        }
        transports.push(new FrontierManagedInferenceTransport(connection.provider, invoker))
      }
    } catch (error) {
      if (error instanceof FrontierRuntimeError) throw error
      if (error instanceof FrontierTransportError) {
        throw new FrontierRuntimeError('TRANSPORT_INVALID', error.message)
      }
      throw error
    }
  }

  const configuredProviders = [...seen].sort() as FrontierInferenceProvider[]
  return Object.freeze({
    gateway: new FrontierInferenceGateway(
      config.deployments,
      transports,
      dependencies.authorizer,
      dependencies.meter,
      dependencies.workOrderVerifier,
      dependencies.streamLeaseVerifier,
    ),
    configuredProviders: Object.freeze(configuredProviders),
  })
}
