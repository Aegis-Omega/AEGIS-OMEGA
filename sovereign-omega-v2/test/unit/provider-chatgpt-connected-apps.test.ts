import { describe, expect, it } from 'vitest'
import {
  DECLARED_PROVIDER_CATALOG_V1,
  buildProviderMeshSnapshotV1,
  selectProviderV1,
} from '../../src/sovereignty/provider-mesh.js'
import {
  observeChatGptConnectedAppV1,
  type ChatGptConnectedAppIdV1,
} from '../../src/sovereignty/provider-adapters/chatgpt-connected-apps.js'

describe('ChatGPT connected-app provider observations v1', () => {
  it('promotes a successful Google Drive read probe to document retrieval availability', async () => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id: 'chatgpt-google-drive',
      operation: 'search',
      outcome: 'READ_SUCCESS',
      result_count: 1,
    }, '20')

    expect(observed.provider_id).toBe('chatgpt-google-drive')
    expect(observed.state).toBe('OBSERVED_AVAILABLE')
    expect(observed.observed_capabilities).toEqual(['DOCUMENT_RETRIEVAL'])
    expect(observed.authority_effect).toBe('NONE')
  })

  it('keeps installed-but-unprobed Gmail non-routable', async () => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id: 'chatgpt-gmail',
      operation: 'plugin_directory_state',
      outcome: 'CONNECTED_NOT_PROBED',
      result_count: 0,
    }, '20')

    expect(observed.state).toBe('ACCOUNT_CONFIGURED')
    expect(observed.observed_capabilities).toEqual([])
  })

  it('keeps a generic connector read failure epistemically unknown', async () => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id: 'chatgpt-google-calendar',
      operation: 'list_calendars',
      outcome: 'READ_FAILURE',
      result_count: 0,
    }, '20')

    expect(observed.state).toBe('UNKNOWN')
    expect(observed.observed_capabilities).toEqual([])
  })


  it.each([
    ['chatgpt-slack', 'slack_read_user_profile', 'COLLABORATION_READ'],
    ['chatgpt-notion', 'fetch_self', 'KNOWLEDGE_BASE_READ'],
    ['chatgpt-linear', 'list_documents', 'WORK_TRACKING_READ'],
    ['chatgpt-hubspot', 'discover_hubspot_schema', 'CRM_READ'],
    ['chatgpt-legalquants-transactional', 'skills_read_lq_start', 'LEGAL_TRANSACTIONAL_GUIDANCE'],
    ['chatgpt-linkedin', 'linkedin_search_people', 'PROFESSIONAL_PROFILE_SEARCH'],
    ['chatgpt-sofa', 'sofa_search_and_get_post', 'AGENT_KNOWLEDGE_READ'],
  ] as const)('maps %s successful read evidence to %s capability', async (connector_id, operation, capability) => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id,
      operation,
      outcome: 'READ_SUCCESS',
      result_count: 1,
    }, '21')

    expect(observed.state).toBe('OBSERVED_AVAILABLE')
    expect(observed.observed_capabilities).toEqual([capability])
    expect(observed.authority_effect).toBe('NONE')
  })

  it('keeps Ads Manager without an accessible account non-routable', async () => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id: 'chatgpt-ads-manager',
      operation: 'list_ad_accounts',
      outcome: 'ACCOUNT_UNAVAILABLE',
      result_count: 0,
    }, '22')

    expect(observed.state).toBe('OBSERVED_UNAVAILABLE')
    expect(observed.observed_capabilities).toEqual([])
    expect(observed.evidence_hash).toBe('6254e17cf94dc9231547e344fb21f81069f6ba1d4808aca2153f469e6852ffcb')
  })

  it('preserves Semrush billing evidence without making SEO routable', async () => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id: 'chatgpt-semrush',
      operation: 'domain_overview',
      outcome: 'BILLING_BLOCKED',
      result_count: 0,
    }, '22')

    expect(observed.state).toBe('BILLING_BLOCKED')
    expect(observed.observed_capabilities).toEqual(['SEO_INTELLIGENCE'])
    expect(observed.evidence_hash).toBe('faf37338f630fe71a9dfbb1ae01dd6a254302391e6ee4b8dc333659655f2d750')

    const snapshot = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [observed])
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['SEO_INTELLIGENCE'],
      allowed_providers: ['chatgpt-semrush'],
      current_generation: '22',
      max_observation_age_generations: '1',
    })

    expect(receipt.outcome).toBe('DENIED')
    expect(receipt.provider_id).toBeNull()
    expect(receipt.denial_codes).toContain('PROVIDER_NOT_OBSERVED_AVAILABLE')
  })

  it('keeps Blockscout network reachability below blockchain-data availability', async () => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id: 'chatgpt-blockscout',
      operation: 'unlock_blockchain_analysis',
      outcome: 'NETWORK_REACHABLE',
      result_count: 1,
    }, '22')

    expect(observed.state).toBe('NETWORK_REACHABLE')
    expect(observed.observed_capabilities).toEqual(['BLOCKCHAIN_DATA_READ'])
    expect(observed.evidence_hash).toBe('76eb44c6502654c34ade8acb44264564674a506e301b878844ba2463b569be12')

    const snapshot = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [observed])
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['BLOCKCHAIN_DATA_READ'],
      allowed_providers: ['chatgpt-blockscout'],
      current_generation: '22',
      max_observation_age_generations: '1',
    })

    expect(receipt.outcome).toBe('DENIED')
    expect(receipt.provider_id).toBeNull()
    expect(receipt.denial_codes).toContain('PROVIDER_NOT_OBSERVED_AVAILABLE')
  })

  it('binds successful LinkedIn search evidence even when result_count is zero', async () => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id: 'chatgpt-linkedin',
      operation: 'linkedin_search_people',
      outcome: 'READ_SUCCESS',
      result_count: 0,
    }, '22')

    expect(observed.state).toBe('OBSERVED_AVAILABLE')
    expect(observed.observed_capabilities).toEqual(['PROFESSIONAL_PROFILE_SEARCH'])
    expect(observed.evidence_hash).toBe('1a8f1c739b9cc211677169170cef489accf0c6287deb559d13caf777abb3975f')
  })

  it.each([
    ['chatgpt-dropbox', 'who_am_i', 'DOCUMENT_RETRIEVAL', 1, '93ef7092b6970a9e527bf6b4719614059ea4648d7131f33faa62b0bf2d0f7cf4'],
    ['chatgpt-sharepoint', 'get_profile', 'DOCUMENT_RETRIEVAL', 1, 'cbcd52517b84fe36e17e4f27df7fe4f37dbf0f88103ab75f901a6c44148b62bd'],
    ['chatgpt-outlook-email', 'get_profile', 'EMAIL_RETRIEVAL', 1, '344faed00555a4d4c5838f346e67867fb11c0ff57ce7d5b659cf74460e5ca974'],
    ['chatgpt-outlook-calendar', 'get_profile', 'CALENDAR_READ', 1, '1b1cca8765b51b3e66ae1cf9297a7bb3dcb7ef839bb6418152b47485803d40e1'],
    ['chatgpt-hugging-face', 'hf_whoami', 'MODEL_HUB_READ', 1, 'b23d5f3c7d10bff92d67eaa2b296fc4ae1b7f9876dc157b7932c34ea0468e94f'],
    ['chatgpt-gitlab', 'get_current_user', 'REPOSITORY_READ', 1, '7eae5f7bedf2f8066ae09626dcc32d3ee11158e65d20f9a335dcea309653ac40'],
    ['chatgpt-vercel', 'list_teams', 'DEPLOYMENT_PLATFORM_READ', 0, 'b00fc42d3e8ee52d62af3b2a919d567ca861f7dce69e339a69c69a118e313a77'],
  ] as const)('binds %s live probe into the provider mesh', async (connector_id, operation, capability, result_count, evidence_hash) => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id,
      operation,
      outcome: 'READ_SUCCESS',
      result_count,
    }, '23')

    expect(observed.state).toBe('OBSERVED_AVAILABLE')
    expect(observed.observed_capabilities).toEqual([capability])
    expect(observed.evidence_hash).toBe(evidence_hash)
    expect(observed.authority_effect).toBe('NONE')
  })

  it('keeps Scite monthly MCP quota exhaustion visible and non-routable', async () => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id: 'chatgpt-scite',
      operation: 'search_literature',
      outcome: 'QUOTA_EXHAUSTED',
      result_count: 0,
    }, '23')

    expect(observed.state).toBe('OBSERVED_UNAVAILABLE')
    expect(observed.observed_capabilities).toEqual(['SCIENTIFIC_LITERATURE_READ'])
    expect(observed.evidence_hash).toBe('1d35d8cb86dd306bbbdc83a437efcc096cb782868b32541f0757ace321af70e3')

    const snapshot = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [observed])
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['SCIENTIFIC_LITERATURE_READ'],
      allowed_providers: ['chatgpt-scite'],
      current_generation: '23',
      max_observation_age_generations: '1',
    })

    expect(receipt.outcome).toBe('DENIED')
    expect(receipt.provider_id).toBeNull()
    expect(receipt.denial_codes).toContain('PROVIDER_NOT_OBSERVED_AVAILABLE')
  })

  it.each([
    ['chatgpt-canva', 'search', 'DESIGN_WORKSPACE_READ', 0, 'e0c301935999a5f94cf6a8353ed8c795cfd56ff0fe4e1562ed9570e383d192d5'],
    ['chatgpt-figma', 'whoami', 'DESIGN_WORKSPACE_READ', 1, '2543eb1234543c9ba18e7b035a7113960f1f425804dda863de88499356789e6d'],
    ['chatgpt-adobe', 'asset_search', 'CREATIVE_ASSET_READ', 0, '39ee1b6bc03b5e41c52f3c55227acd89f73aa76908d0c572f9cfc94769cbf84b'],
    ['chatgpt-gamma', 'get_gammas', 'PRESENTATION_WORKSPACE_READ', 1, '0f380d7d1c6bef717c77db41e675ce42e85a7cc7a2ac870c0a71e0ee9fe1b6ad'],
    ['chatgpt-airtable', 'list_bases', 'OPERATIONS_DATA_READ', 1, 'e8fc330000d02382f3a3b4501e680db48b465453a40720d41d708aea0d6ac31b'],
    ['chatgpt-statsig', 'get_context', 'EXPERIMENTATION_PLATFORM_READ', 1, '1576825b546c1ef716afb23978489a259e7ccf32b152cdc6ee43f29cba29bd73'],
    ['chatgpt-resend', 'list_domains', 'EMAIL_DELIVERY_READ', 0, '988592ad34c81202d8fc04fd3c77325dcabbde79d5a5931b8cbc6d180686aabf'],
  ] as const)('binds %s design/ops read evidence into the provider mesh', async (connector_id, operation, capability, result_count, evidence_hash) => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id,
      operation,
      outcome: 'READ_SUCCESS',
      result_count,
    }, '24')

    expect(observed.state).toBe('OBSERVED_AVAILABLE')
    expect(observed.observed_capabilities).toEqual([capability])
    expect(observed.evidence_hash).toBe(evidence_hash)
    expect(observed.authority_effect).toBe('NONE')
  })

  it.each([
    ['chatgpt-exa', 'web_search_exa', 'WEB_RESEARCH', 0, '66d739095a2061d4172e8921c447f38848a96ebffb4313a4b7d89847ac4c47d1'],
    ['chatgpt-consensus', 'search', 'SCIENTIFIC_LITERATURE_READ', 0, '1e43d1e6d7fbba5b8f771a8874dfe4db6912268cc86492e9ef3172da8d21624a'],
    ['chatgpt-scispace', 'search_papers', 'SCIENTIFIC_LITERATURE_READ', 10, 'e6d84ccc7c8eb82281d70e88a4c8ff9babcfdd4d0decd0c4513ca05812b8a474'],
    ['chatgpt-alphaxiv', 'discover_papers', 'SCIENTIFIC_LITERATURE_READ', 0, 'd040d1b5be4cee431420319281dd00a266ec1f3bed7d5d7d8f9b7fbcf8b37b5f'],
    ['chatgpt-genomic-intelligence', 'list_models', 'GENOMIC_INTELLIGENCE_READ', 7, '9b55bdad1bdcbc0873d31ada0b27dc3a331a112afaf998ffc28323c4c12d508d'],
    ['chatgpt-powers-index', 'get_app_architecture_overview', 'INSTITUTIONAL_INTELLIGENCE_READ', 1, '4a56f92207fc8e7bf21694d153c4ce5d595de81b3850dd82c1425013848d899c'],
  ] as const)('binds %s research/intelligence read evidence into the provider mesh', async (connector_id, operation, capability, result_count, evidence_hash) => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id,
      operation,
      outcome: 'READ_SUCCESS',
      result_count,
    }, '25')

    expect(observed.state).toBe('OBSERVED_AVAILABLE')
    expect(observed.observed_capabilities).toEqual([capability])
    expect(observed.evidence_hash).toBe(evidence_hash)
    expect(observed.authority_effect).toBe('NONE')
  })

  it.each([
    ['chatgpt-railway', 'whoami', 'CLOUD_INFRASTRUCTURE_READ', 1, 'b5dc3d1841f785352b7462828e81c63b4db8a95b2f7fd31ef3b2d1d5e7c4757a'],
    ['chatgpt-digitalocean', 'account_get_information', 'CLOUD_INFRASTRUCTURE_READ', 1, '58dbe212e9cd9dcc89297aca25c1a0a81bc0ea713e46539854abe270467d6780'],
    ['chatgpt-neon', 'list_organizations', 'DATABASE_PLATFORM_READ', 0, '8365125b2ee2f663daf612eea06d1f0cab30e16b932d495e7d762067c6c6960b'],
    ['chatgpt-clickhouse', 'get_organizations', 'DATABASE_PLATFORM_READ', 0, '6d81e966b8d1a3ab34e5370dc9a8c5eddd417d28bb322094c0d8118de968a9e4'],
  ] as const)('binds %s infrastructure read evidence into the provider mesh', async (connector_id, operation, capability, result_count, evidence_hash) => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id,
      operation,
      outcome: 'READ_SUCCESS',
      result_count,
    }, '26')

    expect(observed.state).toBe('OBSERVED_AVAILABLE')
    expect(observed.observed_capabilities).toEqual([capability])
    expect(observed.evidence_hash).toBe(evidence_hash)
    expect(observed.authority_effect).toBe('NONE')
  })

  it.each([
    ['chatgpt-wolfram', 'wolfram_context', 'SYMBOLIC_COMPUTE', 1, '3f6791cae75c8fa7f83dca609c975eb2b52fe63d06b4fb03d131a8f2cd656e7b'],
    ['chatgpt-tavily', 'tavily_search', 'WEB_RESEARCH', 1, '7d0eb83e957ccb37c31c6a2d65f17c5aa1ffdbbbe61c45790ef6b031e9c8a663'],
    ['chatgpt-zoom', 'search_meetings', 'MEETING_KNOWLEDGE_READ', 0, '6a4763ab8c5333cb2fbc6631f86934fd12fcbe566e0c02045ad14f4f703dd276'],
  ] as const)('binds %s compute/web/meeting read evidence into the provider mesh', async (connector_id, operation, capability, result_count, evidence_hash) => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id,
      operation,
      outcome: 'READ_SUCCESS',
      result_count,
    }, '27')

    expect(observed.state).toBe('OBSERVED_AVAILABLE')
    expect(observed.observed_capabilities).toEqual([capability])
    expect(observed.evidence_hash).toBe(evidence_hash)
    expect(observed.authority_effect).toBe('NONE')
  })

  it('keeps Granola without an account non-routable', async () => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id: 'chatgpt-granola',
      operation: 'get_account_info',
      outcome: 'ACCOUNT_UNAVAILABLE',
      result_count: 0,
    }, '27')

    expect(observed.state).toBe('OBSERVED_UNAVAILABLE')
    expect(observed.observed_capabilities).toEqual([])
    expect(observed.evidence_hash).toBe('0c20d390ea46f898457a80210a914bda414b1f35f94b7294a90ad472a011d3d6')
  })

  it('rejects an unknown connector instead of accepting caller-authored capability claims', async () => {
    await expect(observeChatGptConnectedAppV1({
      connector_id: 'chatgpt-unknown' as ChatGptConnectedAppIdV1,
      operation: 'read',
      outcome: 'READ_SUCCESS',
      result_count: 1,
    }, '20')).rejects.toThrow('unsupported ChatGPT connected app')
  })

  it('routes document retrieval only after successful connector evidence', async () => {
    const drive = await observeChatGptConnectedAppV1({
      connector_id: 'chatgpt-google-drive',
      operation: 'search',
      outcome: 'READ_SUCCESS',
      result_count: 1,
    }, '20')

    const snapshot = await buildProviderMeshSnapshotV1(
      DECLARED_PROVIDER_CATALOG_V1,
      [drive],
    )
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['DOCUMENT_RETRIEVAL'],
      allowed_providers: ['chatgpt-google-drive'],
      current_generation: '20',
      max_observation_age_generations: '1',
    })

    expect(receipt.outcome).toBe('SELECTED')
    expect(receipt.provider_id).toBe('chatgpt-google-drive')
    expect(receipt.authority_effect).toBe('NONE')
  })
})
