#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL is required}"

MIGRATION="supabase/migrations/20260902163600_cognitive_recovery_replay_state.sql"
REPOSITORY_ID="Aegis-Omega/AEGIS-OMEGA"
REQ_A="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
REQ_B="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
CAND_A="1111111111111111111111111111111111111111"
CAND_B="2222222222222222222222222222222222222222"
APPROVAL_A="cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
APPROVAL_B="dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
ZERO_UUID="00000000-0000-0000-0000-000000000001"

psqlq() {
  psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -Atq "$@"
}

fail() {
  echo "ATOMIC_REPLAY_TEST_FAILURE: $*" >&2
  exit 1
}

[[ -f "$MIGRATION" ]] || fail "missing migration: $MIGRATION"

# Migration grants only the service_role RPC surface. Create the role locally so
# the exact production DDL can be exercised in the ephemeral Postgres service.
psqlq -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN CREATE ROLE service_role NOLOGIN; END IF; END \$\$;"
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -f "$MIGRATION" >/dev/null

init_a="$(psqlq -F '|' -c "SELECT request_digest,state,generation FROM initialize_cognitive_recovery_replay('$REQ_A','$REPOSITORY_ID','$CAND_A','$APPROVAL_A');")"
[[ "$init_a" == "$REQ_A|UNUSED|0" ]] || fail "request A initialization mismatch: $init_a"

# Idempotent initialization with identical bindings returns the same state.
init_a_again="$(psqlq -F '|' -c "SELECT request_digest,state,generation FROM initialize_cognitive_recovery_replay('$REQ_A','$REPOSITORY_ID','$CAND_A','$APPROVAL_A');")"
[[ "$init_a_again" == "$REQ_A|UNUSED|0" ]] || fail "idempotent initialization mismatch: $init_a_again"

# The same request digest may never be rebound to another candidate.
rebind_count="$(psqlq -c "SELECT count(*) FROM initialize_cognitive_recovery_replay('$REQ_A','$REPOSITORY_ID','$CAND_B','$APPROVAL_A');")"
[[ "$rebind_count" == "0" ]] || fail "request digest binding was rewritten"

# Two concurrent callers race on UNUSED generation 0. Exactly one may reserve.
r1="$(mktemp)"
r2="$(mktemp)"
trap 'rm -f "$r1" "$r2"' EXIT
psqlq -F '|' -c "SELECT request_digest,state,generation,reservation_id FROM reserve_cognitive_recovery_replay('$REQ_A',0);" >"$r1" &
p1=$!
psqlq -F '|' -c "SELECT request_digest,state,generation,reservation_id FROM reserve_cognitive_recovery_replay('$REQ_A',0);" >"$r2" &
p2=$!
wait "$p1"
wait "$p2"

winner_lines=$(( $(grep -c . "$r1" || true) + $(grep -c . "$r2" || true) ))
[[ "$winner_lines" -eq 1 ]] || fail "concurrent reserve produced $winner_lines winners"
winner="$(cat "$r1" "$r2" | grep .)"
IFS='|' read -r winner_req winner_state winner_generation reservation_id <<<"$winner"
[[ "$winner_req" == "$REQ_A" && "$winner_state" == "RESERVED" && "$winner_generation" == "1" ]] \
  || fail "unexpected reserve winner: $winner"
[[ "$reservation_id" =~ ^[0-9a-f-]{36}$ ]] || fail "missing reservation id: $reservation_id"

# Once reserved, neither stale nor current-generation reserve attempts may mint
# a second reservation.
[[ "$(psqlq -c "SELECT count(*) FROM reserve_cognitive_recovery_replay('$REQ_A',0);")" == "0" ]] \
  || fail "stale generation reserve succeeded"
[[ "$(psqlq -c "SELECT count(*) FROM reserve_cognitive_recovery_replay('$REQ_A',1);")" == "0" ]] \
  || fail "second reserve succeeded"

# Wrong reservation identity cannot consume.
[[ "$(psqlq -c "SELECT count(*) FROM consume_cognitive_recovery_replay('$REQ_A','$ZERO_UUID',1);")" == "0" ]] \
  || fail "wrong reservation consumed request"

consumed="$(psqlq -F '|' -c "SELECT request_digest,state,generation FROM consume_cognitive_recovery_replay('$REQ_A','$reservation_id',1);")"
[[ "$consumed" == "$REQ_A|CONSUMED|2" ]] || fail "consume mismatch: $consumed"
[[ "$(psqlq -c "SELECT count(*) FROM consume_cognitive_recovery_replay('$REQ_A','$reservation_id',2);")" == "0" ]] \
  || fail "double consume succeeded"

# UNKNOWN is terminal for normal replay operations.
init_b="$(psqlq -F '|' -c "SELECT request_digest,state,generation FROM initialize_cognitive_recovery_replay('$REQ_B','$REPOSITORY_ID','$CAND_B','$APPROVAL_B');")"
[[ "$init_b" == "$REQ_B|UNUSED|0" ]] || fail "request B initialization mismatch: $init_b"
reserved_b="$(psqlq -F '|' -c "SELECT request_digest,state,generation,reservation_id FROM reserve_cognitive_recovery_replay('$REQ_B',0);")"
IFS='|' read -r _ _ generation_b reservation_b <<<"$reserved_b"
[[ "$generation_b" == "1" ]] || fail "request B reserve mismatch: $reserved_b"
unknown_b="$(psqlq -F '|' -c "SELECT request_digest,state,generation FROM mark_cognitive_recovery_replay_unknown('$REQ_B','$reservation_b',1);")"
[[ "$unknown_b" == "$REQ_B|UNKNOWN|2" ]] || fail "UNKNOWN transition mismatch: $unknown_b"
[[ "$(psqlq -c "SELECT count(*) FROM reserve_cognitive_recovery_replay('$REQ_B',2);")" == "0" ]] \
  || fail "UNKNOWN request returned to reserve path"
[[ "$(psqlq -c "SELECT count(*) FROM consume_cognitive_recovery_replay('$REQ_B','$reservation_b',2);")" == "0" ]] \
  || fail "UNKNOWN request consumed"

# The table is RLS-protected and the RPCs are not executable by PUBLIC.
rls="$(psqlq -c "SELECT relrowsecurity FROM pg_class WHERE oid='public.cognitive_recovery_replay_state'::regclass;")"
[[ "$rls" == "t" ]] || fail "RLS is not enabled"
for signature in \
  "initialize_cognitive_recovery_replay(text,text,text,text)" \
  "reserve_cognitive_recovery_replay(text,bigint)" \
  "consume_cognitive_recovery_replay(text,uuid,bigint)" \
  "mark_cognitive_recovery_replay_unknown(text,uuid,bigint)"
do
  public_exec="$(psqlq -c "SELECT EXISTS (SELECT 1 FROM pg_proc p CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl, acldefault('f', p.proowner))) a WHERE p.oid='public.$signature'::regprocedure AND a.grantee=0 AND a.privilege_type='EXECUTE');")"
  [[ "$public_exec" == "f" ]] || fail "PUBLIC can execute $signature"
done

echo "ATOMIC_REPLAY_STORE_TEST_STATUS=GREEN"
