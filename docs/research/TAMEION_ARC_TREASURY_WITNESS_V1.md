# TAMEION_ARC_TREASURY_WITNESS_V1

Status: **DRAFT / EVIDENCE_ONLY**  
Authority effect: **NONE**  
Funds moved by this module: **NONE**

## Purpose

Bind an already-authorized AEGIS treasury intent to a later observed settlement
on Circle Arc without granting this repository any wallet, signing, custody, or
transaction-broadcast authority.

This is the smallest bridge between the existing AEGIS authority/receipt model
and the Tameion hackathon's accounting/ERP + stablecoin problem space.

## External Arc anchors observed during preparation

Blockscout returned the following live chain identities and tips on 2026-09-21:

- Arc Mainnet — chain id `5042`, native currency USDC; observed block
  `22076796` at `2026-09-21T22:15:41Z`.
- Arc Testnet — chain id `5042002`, native currency USDC; observed block
  `63312953` at `2026-09-21T21:28:11Z`.

These observations establish that the Arc chains are externally addressable.
They do **not** prove finality, token-contract semantics, account ownership, or
that AEGIS controls any wallet.

## Sponsor-first / zero-operator-funds execution path

Official Arc documentation states:

- Arc Testnet uses USDC as the gas token.
- Testnet USDC can be requested from the Circle Faucet.
- Testnet USDC has no real-world value and must not be used in production.
- Circle App Kit supports USDC sends on `Arc_Testnet`.
- Circle Contracts API supports monitoring contract events on Arc Testnet.
- The optional USDC ERC-20 interface is
  `0x3600000000000000000000000000000000000000` and uses 6 decimals.

References:

- https://docs.arc.network/arc/tutorials/deploy-on-arc
- https://docs.arc.network/app-kit
- https://docs.arc.network/arc/tutorials/monitor-contract-events
- https://docs.arc.network/arc/references/contract-addresses

Therefore the next executable integration target is **Arc Testnet only**, funded
with faucet/test credits rather than operator capital. No mainnet transaction is
required to validate the witness path.

Important unit boundary: `amount_microunits` in this module refers to the
6-decimal USDC transfer interface, not Arc native gas precision. Arc docs warn
that native USDC gas accounting uses 18 decimals while the ERC-20 interface uses
6 decimals; these values must not be mixed.

## Deterministic transition

```
AEGIS policy decision
        +
MutationReceipt root
        ↓
ArcTreasuryIntent root
        ↓
external settlement occurs outside this module
        ↓
ArcSettlementObservation
        ↓
field equality checks:
  chain_id
  amount_microunits
  destination
  status == CONFIRMED
        ↓
ArcTreasuryWitness root
```

The witness is content-addressed and deterministic over the canonical intent and
observation payloads.

## Fail-closed conditions

The module denies witness construction when:

- chain id is not Arc Mainnet or Arc Testnet;
- asset is not USDC;
- amount is non-positive;
- EVM destination or transaction hash is malformed;
- authority or mutation receipt root is malformed;
- observed chain differs from the authorized chain;
- observed amount differs from the authorized amount;
- observed destination differs from the authorized destination;
- observed transaction is not marked `CONFIRMED`.

## Explicit non-claims

This module does not:

- hold private keys;
- sign transactions;
- broadcast transactions;
- move USDC;
- assert blockchain finality independently;
- verify the USDC token contract;
- prove signer identity;
- prove that AEGIS originated a transaction;
- create financial authority;
- provide custody or treasury management.

A later execution adapter may consume an admitted AEGIS authority decision and
submit a transaction, but that adapter must live behind the existing D3/D4
consequential-action path, explicit approval, writer lease/fencing, durable
execution registry, and external-action idempotency.

## Tameion fit

The hackathon invite describes accounting/ERP agents using stablecoins,
milestone-based settlement, and replayable append-only financial decision
records. This lane targets only the evidence-binding portion of that problem:
**authorized intent → externally observed Arc settlement → replayable witness**.

No sponsor credits or operator funds are consumed by this PR.
