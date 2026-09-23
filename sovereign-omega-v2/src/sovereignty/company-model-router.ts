export type CompanyModelV1 =
  | 'gpt-5.6-luna'
  | 'gpt-5.6-terra'
  | 'gpt-5.6-sol'
  | 'gpt-6-astra'

export type CompanyWorkClassV1 =
  | 'INTAKE'
  | 'ROUTINE'
  | 'DEEP_REASONING'
  | 'FRONTIER_AGENT'

export interface CompanyModelRouteInputV1 {
  readonly work_class: CompanyWorkClassV1
  readonly tools_required: boolean
  readonly long_context?: boolean
  readonly computer_use?: boolean
  readonly independent_verifier?: boolean
}

export interface CompanyModelRouteV1 {
  readonly model: CompanyModelV1
  readonly reason: string
  readonly complimentary_eligible_model_group:
    | '10M_OR_2_5M'
    | '1M_OR_250K'
    | 'NOT_LISTED'
  readonly tool_use_excluded_from_complimentary: boolean
  readonly budget_class: 'LOW' | 'MEDIUM' | 'HIGH' | 'FRONTIER'
  readonly authority_effect: 'NONE'
}

export function routeCompanyModelV1(
  input: CompanyModelRouteInputV1,
): CompanyModelRouteV1 {
  if (
    !input ||
    !['INTAKE', 'ROUTINE', 'DEEP_REASONING', 'FRONTIER_AGENT'].includes(input.work_class)
  ) {
    throw new TypeError('invalid work_class')
  }

  let model: CompanyModelV1
  let reason: string
  let group: CompanyModelRouteV1['complimentary_eligible_model_group']
  let budget: CompanyModelRouteV1['budget_class']

  if (input.computer_use || input.work_class === 'FRONTIER_AGENT') {
    model = 'gpt-6-astra'
    reason = 'frontier end-to-end agent or computer-use workload'
    group = 'NOT_LISTED'
    budget = 'FRONTIER'
  } else if (input.independent_verifier || input.work_class === 'DEEP_REASONING') {
    model = 'gpt-5.6-sol'
    reason = 'hard reasoning or independent verification'
    group = '1M_OR_250K'
    budget = 'HIGH'
  } else if (input.work_class === 'ROUTINE' || input.long_context || input.tools_required) {
    model = 'gpt-5.6-terra'
    reason = input.tools_required
      ? 'routine tool-using work; tool use is budgeted as non-complimentary'
      : 'balanced routine operations'
    group = '10M_OR_2_5M'
    budget = 'MEDIUM'
  } else {
    model = 'gpt-5.6-luna'
    reason = 'high-volume intake/extraction'
    group = '10M_OR_2_5M'
    budget = 'LOW'
  }

  return Object.freeze({
    model,
    reason,
    complimentary_eligible_model_group: group,
    tool_use_excluded_from_complimentary: input.tools_required,
    budget_class: budget,
    authority_effect: 'NONE',
  })
}
