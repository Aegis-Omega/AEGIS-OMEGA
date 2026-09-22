# TAMEION_OPENMETER_ARC_RUNBOOK_V1

Status: **DRAFT / PRE-HACKATHON PROTOTYPE**  
Authority effect: **NONE**  
Default network effect: **NONE**  
Mainnet funds: **FORBIDDEN IN THIS LANE**

## Goal

Demonstrate the Tameion "let the meter settle itself" concept without collapsing
metering, authority, signing, settlement, and reconciliation into one opaque
agent action.

The evidence path is:

```
OpenMeter usage event
        ↓
metered usage observation
        ↓
explicit testnet settlement policy
        ↓
payment obligation
        ↓
AEGIS policy decision (must already be ADMITTED D3/D4)
        ↓
Arc treasury intent
        ↓
Arc Testnet transfer plan
        ↓
unsigned USDC calldata
        ↓
[external signer/broadcast boundary — NOT IMPLEMENTED HERE]
        ↓
observed Arc settlement
        ↓
settlement witness
        ↓
post-settlement calibration
        ↓
metered evidence-chain root
```

## Current official integration anchors

Verified against the current public documentation during development:

- Arc Testnet chain id: `5042002`.
- Arc Testnet RPC: `https://rpc.testnet.arc.io`.
- Arc uses USDC as the native gas asset.
- Optional Arc USDC ERC-20 interface:
  `0x3600000000000000000000000000000000000000`.
- The ERC-20 interface uses 6 decimals.
- Arc native USDC gas accounting uses 18 decimals of precision; native-gas units
  and ERC-20 transfer microunits must never be mixed directly.
- Circle's public faucet currently supports Arc Testnet and supplies free testnet
  USDC. Testnet tokens have no real-world value.
- OpenMeter's current quickstart supports event-driven usage metering with a
  `request` event and an API-request COUNT meter. New integrations should use
  the current OpenMeter API surface rather than depending on historical API
  versions.

References:

- https://docs.arc.io/arc/tutorials/deploy-on-arc
- https://docs.arc.io/arc/references/contract-addresses
- https://faucet.circle.com/
- https://openmeter.io/docs/metering/quickstart
- https://openmeter.io/docs/metering/guides/common-examples
- https://openmeter.io/developers

## Repository components

### Source normalization

`harness/sdk/tameion_openmeter_bridge.py`

Builds:

- `OpenMeterUsageObservation`
- `OpenMeterSettlementPolicy`
- `OpenMeterPaymentObligation`
- `OpenMeterArcIntentBinding`

The bridge rejects:

- non-metered inputs;
- meter/policy mismatch;
- non-positive usage or price;
- obligation amounts above the explicit demo cap;
- Arc mainnet;
- non-USDC assets;
- real-value enablement;
- broadcast enablement.

### Admitted execution planning

`harness/sdk/arc_treasury_execution.py`

Requires an already-produced AEGIS `PolicyDecision` with:

- `outcome == ADMITTED`;
- action class `D3` or `D4`;
- decision root equal to the treasury intent's authority root.

This module does not produce an approval and cannot promote a denied decision.

### Unsigned transaction encoding

`harness/sdk/arc_erc20_call.py`

Produces deterministic `transfer(address,uint256)` calldata only.

Invariant:

```
signer_attached = false
broadcast_allowed = false
authority_effect = NONE
```

### Pre-settlement packet

`harness/sdk/tameion_presettlement_bundle.py`

Binds the exact OpenMeter obligation and source binding to the exact admitted
Arc transfer plan and unsigned call. Event swapping, plan swapping, authority
root swapping, amount drift, destination drift, or idempotency drift fail closed.

### Settlement witness

`harness/sdk/arc_treasury_witness.py`

Accepts only an already-observed settlement whose:

- chain matches;
- amount matches;
- destination matches;
- status is `CONFIRMED`.

It does not independently prove finality, signer identity, wallet ownership, or
that AEGIS originated the transaction.

### Metered end-to-end closure

`harness/sdk/tameion_metered_evidence_chain.py`

Binds:

```
pre_settlement_bundle_root
+ settlement_witness_root
+ calibration_root
+ optional notebook_evidence_root
→ metered_evidence_chain_root
```

### Offline demo CLI

`harness/sdk/tameion_demo_cli.py`

The CLI performs no network calls. It accepts JSON input and emits canonical JSON.

Dry-run state:

```
status = PRE_SETTLEMENT_READY
network_effect = NONE
authority_effect = NONE
```

If a matching, already-observed settlement is supplied:

```
status = SETTLEMENT_RECONCILED
```

The CLI still does not sign or broadcast.

## Evidence classes

Do not collapse these states:

1. **SYNTHETIC_TEST_FIXTURE**
   - unit-test hashes, addresses, transaction hashes, block numbers;
   - proves validation logic only.

2. **PRE_SETTLEMENT_READY**
   - real metered input may be present;
   - exact obligation/intent/plan/call roots exist;
   - no settlement is claimed.

3. **HOSTED_REPLAY_EXECUTED**
   - requires a workflow job with an actual runner and executed steps.

4. **SETTLEMENT_OBSERVED**
   - requires a real Arc Testnet transaction observation.

5. **SETTLEMENT_RECONCILED**
   - requires the observation to bind exactly to the admitted source/plan.

## Current hosted replay boundary

The dedicated `Tameion Arc Evidence Replay` workflow was added because the
repository-wide GitHub workflows were reporting top-level failures without
executed steps.

Observed dedicated run:

- workflow: `Tameion Arc Evidence Replay`
- run id: `35797742015`
- exact head: `00d66b18fa1b0aa2f4c70a115a076d57f84853e9`
- workflow conclusion: `failure`
- job id: `106980836822`
- job conclusion: `failure`
- executed steps: **0**
- job logs: **not available**

Disposition:

```
HOSTED_REPLAY_EXECUTED = false
CODE_FAILURE_FROM_THIS_RUN = NOT_ESTABLISHED
```

This historical receipt applies only to the SHA above. Any later head requires a
fresh hosted replay.

## Hackathon eligibility boundary

The invitation confirms the event and problem space, but the repository does
not yet contain organizer confirmation of:

- exact judging criteria;
- final submission format;
- eligibility details;
- whether pre-event code is allowed;
- sponsor credits/grants and their conditions.

Until those items are confirmed, this repository should describe the work as a
**pre-hackathon prototype** rather than an eligible or accepted submission.
