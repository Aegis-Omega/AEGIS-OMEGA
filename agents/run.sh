#!/usr/bin/env bash
# AEGIS-Ω Agent Coordinator — Quick-start launcher
# Usage: ./agents/run.sh [command] [task_or_args...]
# Run from repo root or any subdirectory.
#
# Examples:
#   ./agents/run.sh list
#   ./agents/run.sh backend
#   ./agents/run.sh engineering "Diagnose CI failure on PR #136"
#   ./agents/run.sh ai-safety "Assess alignment properties against AEGIS constitutional invariants"
#   ./agents/run.sh biz-dev "Prepare Anthropic partnership technical brief"
#   ./agents/run.sh compliance "Map AEGIS against EU AI Act Article 12"
#   ./agents/run.sh dispatch anthropic_partnership '{"context":"Mythos gap identified"}'
#   ./agents/run.sh register-managed
#   ./agents/run.sh register-vertex --mode proxy
#   ./agents/run.sh validate-vertex

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

PYTHON="${PYTHON:-python3}"

# Install deps if needed
if ! $PYTHON -c "import httpx, yaml" 2>/dev/null; then
    echo "[agents] Installing dependencies..."
    pip install -q -r "$SCRIPT_DIR/requirements.txt"
fi

cd "$REPO_ROOT"

export PROXY_URL="${PROXY_URL:-http://localhost:8080}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379}"
export AEGIS_DEFAULT_MODEL="${AEGIS_DEFAULT_MODEL:-claude-opus-4-8}"

COORD="$PYTHON -m agents.coordinator"

case "${1:-help}" in
  # ── Discovery ────────────────────────────────────────────────────────────
  list)
    $COORD list
    ;;

  backend)
    $COORD backend
    ;;

  # ── Research & Science ───────────────────────────────────────────────────
  ai-research)
    $COORD run --role ai_research \
      --task "${2:-Evaluate the constitutional governance gap in Mythos-class models}"
    ;;

  ai-safety)
    $COORD run --role ai_safety \
      --task "${2:-Assess alignment properties against AEGIS constitutional invariants}"
    ;;

  applied-science)
    $COORD run --role applied_science \
      --task "${2:-Research evaluation methodology for constitutional compliance}"
    ;;

  # ── Engineering ──────────────────────────────────────────────────────────
  engineering)
    $COORD run --role engineering \
      --task "${2:-Diagnose CI failure and propose fix following RALPH protocol}"
    ;;

  platform)
    $COORD run --role platform_engineering \
      --task "${2:-Review infrastructure scaling strategy for constitutional substrate}"
    ;;

  hardware)
    $COORD run --role hardware_engineering \
      --task "${2:-Evaluate AMD RX 570 ROCm configuration for aegis-cl-psi}"
    ;;

  supply-chain)
    $COORD run --role supply_chain \
      --task "${2:-Audit dependency supply chain for constitutional risk vectors}"
    ;;

  # ── Data ──────────────────────────────────────────────────────────────────
  data-labeling)
    $COORD run --role data_labeling \
      --task "${2:-Design constitutional labeling schema for alignment training data}"
    ;;

  data-governance)
    $COORD run --role data_governance \
      --task "${2:-Assess data pipeline constitutional compliance}"
    ;;

  # ── Product ───────────────────────────────────────────────────────────────
  product)
    $COORD run --role product_management \
      --task "${2:-Define product requirements for constitutional governance feature}"
    ;;

  design)
    $COORD run --role product_design \
      --task "${2:-Design consciousness substrate UI for hub landing page}"
    ;;

  devex)
    $COORD run --role devex \
      --task "${2:-Improve developer onboarding for AEGIS constitutional API}"
    ;;

  # ── Security ─────────────────────────────────────────────────────────────
  security)
    $COORD run --role cybersecurity \
      --task "${2:-Scan for constitutional boundary breaches}"
    ;;

  it)
    $COORD run --role it_systems \
      --task "${2:-Audit internal systems for compliance with constitutional boundaries}"
    ;;

  internal-ai)
    $COORD run --role internal_ai_enablement \
      --task "${2:-Design internal AI tooling governed by constitutional substrate}"
    ;;

  # ── Trust, Safety & Ethics ────────────────────────────────────────────────
  trust-safety)
    $COORD run --role trust_safety \
      --task "${2:-Evaluate content policy against constitutional law}"
    ;;

  ethics)
    $COORD run --role ai_ethics \
      --task "${2:-Assess ethical implications of autonomous agent deployment}"
    ;;

  # ── Legal & Compliance ────────────────────────────────────────────────────
  compliance)
    $COORD run --role compliance \
      --task "${2:-Map AEGIS architecture against EU AI Act Article 12 requirements}"
    ;;

  policy)
    $COORD run --role policy_affairs \
      --task "${2:-Draft policy position on constitutional AI governance}"
    ;;

  # ── Commercial ────────────────────────────────────────────────────────────
  communications)
    $COORD run --role communications \
      --task "${2:-Draft press release on AEGIS constitutional governance milestone}"
    ;;

  marketing)
    $COORD run --role marketing \
      --task "${2:-Create constitutional AI governance content for enterprise audience}"
    ;;

  biz-dev)
    $COORD run --role biz_dev \
      --task "${2:-Prepare Anthropic partnership technical brief}"
    ;;

  sales)
    $COORD run --role sales \
      --task "${2:-Draft enterprise outreach for constitutional AI governance offering}"
    ;;

  solutions)
    $COORD run --role solutions_engineering \
      --task "${2:-Design integration architecture for constitutional proxy deployment}"
    ;;

  customer-success)
    $COORD run --role customer_success \
      --task "${2:-Develop onboarding plan for enterprise constitutional governance}"
    ;;

  support)
    $COORD run --role support \
      --task "${2:-Triage constitutional governance support request}"
    ;;

  devrel)
    $COORD run --role devrel \
      --task "${2:-Create technical tutorial on AEGIS constitutional API}"
    ;;

  partnerships)
    $COORD run --role partnerships \
      --task "${2:-Evaluate Vertex AI Model Garden partnership structure}"
    ;;

  # ── Finance ───────────────────────────────────────────────────────────────
  finance)
    $COORD run --role finance \
      --task "${2:-Model unit economics for constitutional governance SaaS offering}"
    ;;

  corp-dev)
    $COORD run --role corporate_development \
      --task "${2:-Evaluate M&A targets for constitutional AI governance expansion}"
    ;;

  strategy)
    $COORD run --role strategy \
      --task "${2:-Define 12-month strategy for constitutional AI governance market}"
    ;;

  # ── People & Talent ───────────────────────────────────────────────────────
  talent)
    $COORD run --role talent_acquisition \
      --task "${2:-Design hiring strategy for constitutional AI governance team}"
    ;;

  people)
    $COORD run --role people_ops \
      --task "${2:-Design operating principles for autonomous agent org}"
    ;;

  workplace)
    $COORD run --role workplace \
      --task "${2:-Plan distributed workspace for autonomous agent organization}"
    ;;

  # ── Enablement ────────────────────────────────────────────────────────────
  education)
    $COORD run --role education \
      --task "${2:-Create constitutional AI governance curriculum}"
    ;;

  # ── Mythos Cognitive Substrate (tier-0 apex agents) ───────────────────────
  deep-research)
    $COORD run --role deep_researcher \
      --task "${2:-Exhaustively research INT4 LUT-KAN viability; emit citable claims}"
    ;;

  corpus)
    $COORD run --role corpus_ingestor \
      --task "${2:-Run 5-phase RALPH ARBITRATION on the latest research findings}"
    ;;

  batch)
    $COORD run --role batch_processor \
      --task "${2:-Partition corpus findings into Fibonacci-cadence RALPH batches}"
    ;;

  chronology)
    $COORD run --role chronologist \
      --task "${2:-Narrate the adaptive lineage; produce the retrospective entry}"
    ;;

  # ── Mythos pipeline: deep-research → corpus → batch → chronology ───────────
  pipeline)
    $PYTHON -m agents.cognitive_pipeline run --topic "${2:-INT4 LUT-KAN viability}" "${@:3}"
    ;;

  pipeline-demo)
    $PYTHON -m agents.cognitive_pipeline demo
    ;;

  arbitrate)
    $PYTHON -m agents.cognitive_pipeline score --claim "${2:-deterministic SHA-256 hash chain}"
    ;;

  # ── Revenue engine: the money loop (commercial departments collaborate) ────
  revenue)
    $PYTHON -m agents.revenue_engine run --objective "${2:-Sell AEGIS constitutional governance to AI labs needing EU AI Act compliance}" "${@:3}"
    ;;

  revenue-demo)
    $PYTHON -m agents.revenue_engine demo
    ;;

  revenue-verify)
    $PYTHON -m agents.revenue_engine verify
    ;;

  # ── Event dispatcher ─────────────────────────────────────────────────────
  dispatch)
    EVENT="${2:-github_pr_opened}"
    PAYLOAD="${3:-{\"title\":\"test\",\"number\":1}}"
    $COORD dispatch --event "$EVENT" --payload "$PAYLOAD"
    ;;

  # ── Anthropic partnership event ───────────────────────────────────────────
  partnership)
    $COORD dispatch \
      --event anthropic_partnership \
      --payload '{"context":"Mythos system card published. Constitutional governance gap identified. 5 failure modes resolved by AEGIS boundary enforcement."}'
    ;;

  # ── Registration ─────────────────────────────────────────────────────────
  register-managed)
    $PYTHON -m agents.register_managed "${@:2}"
    ;;

  register-vertex)
    $PYTHON -m agents.register_vertex_adk "${@:2}"
    ;;

  validate-vertex)
    $PYTHON -m agents.register_vertex_adk --validate
    ;;

  # ── Help ──────────────────────────────────────────────────────────────────
  help|*)
    cat <<'EOF'
AEGIS-Ω Agent Coordinator — 34 autonomous AI departments

Usage: ./agents/run.sh <command> [task] [...]

DISCOVERY
  list                    List all 34 departments with capabilities
  backend                 Show active inference backend and registry status

RESEARCH & SCIENCE
  ai-research [task]      AI Research
  ai-safety [task]        AI Safety
  applied-science [task]  Applied Science

ENGINEERING
  engineering [task]      Engineering
  platform [task]         Platform Engineering
  hardware [task]         Hardware Engineering
  supply-chain [task]     Supply Chain

DATA
  data-labeling [task]    Data Labeling
  data-governance [task]  Data Governance

PRODUCT
  product [task]          Product Management
  design [task]           Product Design
  devex [task]            Developer Experience

SECURITY
  security [task]         Cybersecurity
  it [task]               IT Systems
  internal-ai [task]      Internal AI Enablement

TRUST, SAFETY & ETHICS
  trust-safety [task]     Trust & Safety
  ethics [task]           AI Ethics

LEGAL & COMPLIANCE
  compliance [task]       Compliance
  policy [task]           Policy Affairs

COMMERCIAL
  communications [task]   Communications
  marketing [task]        Marketing
  biz-dev [task]          Business Development
  sales [task]            Sales
  solutions [task]        Solutions Engineering
  customer-success [task] Customer Success
  support [task]          Support
  devrel [task]           Developer Relations
  partnerships [task]     Partnerships

FINANCE
  finance [task]          Finance
  corp-dev [task]         Corporate Development
  strategy [task]         Strategy

PEOPLE & TALENT
  talent [task]           Talent Acquisition
  people [task]           People Operations
  workplace [task]        Workplace

ENABLEMENT
  education [task]        Education

EVENTS
  dispatch [event] [json] Route event to constitutional agent mesh
  partnership             Prepare Anthropic partnership brief (multi-agent)

REGISTRATION
  register-managed        Register all 34 agents on Anthropic Managed Agents
  register-vertex [flags] Deploy all 34 agents to Vertex AI (project: aegisomegav1)
  validate-vertex         Validate AnthropicVertex connection to aegisomegav1

Environment:
  ANTHROPIC_API_KEY       Required for managed agents backend
  VERTEX_PROJECT_ID       GCP project (default: aegisomegav1)
  VERTEX_REGION           Vertex region (default: us-east5)
  PROXY_URL               Constitutional proxy URL (default: http://localhost:8080)
  REDIS_URL               Redis URL (default: redis://localhost:6379)

Backend auto-detection priority:
  1. MANAGED_AGENTS  if ANTHROPIC_API_KEY set + agent_registry.json exists
  2. VERTEX_AI       if VERTEX_PROJECT_ID set
  3. DIRECT          constitutional proxy fallback
EOF
    ;;
esac
