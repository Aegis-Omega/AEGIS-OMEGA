#!/usr/bin/env bash
# Disposable PostgreSQL ONLY. No Supabase project changes, model calls or secrets.
# Requires psql with SUPERUSER permissions in an ephemeral test database.
set -euo pipefail
: "${PGHOST:?Set PGHOST to disposable PostgreSQL host}"
: "${PGUSER:?Set PGUSER to disposable PostgreSQL superuser}"
: "${PGDATABASE:?Set PGDATABASE to disposable database}"
: "${PGPORT:?Set PGPORT}"
if [[ "${PGDATABASE}" != "aegis_test" || "${PGUSER}" != "postgres" || "${PGPORT}" != "5432" ||
      -n "${PGSERVICE:-}" || -n "${PGHOSTADDR:-}" ]]; then
  echo "DENIED: only the isolated CI test database is allowed" >&2; exit 4
fi
case "${PGHOST}" in
  localhost|127.0.0.1|::1) ;;
  *) echo "DENIED: nonlocal database host" >&2; exit 4 ;;
esac
psql -X -v ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
SQL
psql -X -v ON_ERROR_STOP=1 -f supabase/migrations/20261010190000_agent_dispatch_claims_v1.sql
psql -X -v ON_ERROR_STOP=1 -f supabase/migrations/20261011052000_agent_result_outbox_v1.sql
psql -X -v ON_ERROR_STOP=1 -f supabase/migrations/20261011070000_agent_result_outbox_retention_v1.sql
psql -X -v ON_ERROR_STOP=1 <<'SQL'
DO $t$
BEGIN
 IF (select count(*) from pg_proc where oid='public.aegis_outbox_purge_expired_v1(integer)'::regprocedure and prosecdef) <> 1 THEN
   RAISE EXCEPTION 'PURGE MUST BE SECURITY DEFINER';
 END IF;
 IF (select pg_get_userbyid(proowner) from pg_proc where oid='public.aegis_outbox_purge_expired_v1(integer)'::regprocedure) <> current_user THEN
   RAISE EXCEPTION 'PURGE OWNER UNEXPECTED';
 END IF;
 IF has_function_privilege('anon','public.aegis_outbox_purge_expired_v1(integer)','EXECUTE')
 OR has_function_privilege('authenticated','public.aegis_outbox_purge_expired_v1(integer)','EXECUTE')
 OR NOT has_function_privilege('service_role','public.aegis_outbox_purge_expired_v1(integer)','EXECUTE')
 THEN RAISE EXCEPTION 'INVALID FUNCTION EXECUTE ACL'; END IF;
 IF has_table_privilege('service_role','public.aegis_agent_result_outbox_v1','DELETE')
 OR has_table_privilege('anon','public.aegis_agent_result_outbox_v1','SELECT')
 OR has_table_privilege('authenticated','public.aegis_agent_result_outbox_v1','SELECT')
 THEN RAISE EXCEPTION 'INVALID TABLE ACL'; END IF;
END $t$;

INSERT INTO public.aegis_agent_dispatch_claims_v1(event_digest)
VALUES(repeat('a',64)),(repeat('c',64)),(repeat('e',64));
INSERT INTO public.aegis_agent_result_outbox_v1
 (event_digest,destination_digest,ciphertext_b64,iv_b64,delivery_state,attempt_id,attempt_count,expires_at)
VALUES
 (repeat('a',64),repeat('b',64),'YQ==','MTIz','SENDING','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',1,now()-interval '25 hours'),
 (repeat('c',64),repeat('d',64),'Yg==','MTIz','READY',null,0,now()+interval '24 hours'),
 (repeat('e',64),repeat('f',64),'Yw==','MTIz','READY',null,0,now()+interval '24 hours');

-- Execute the RPCs AS service_role, not just as the migration superuser.
SET ROLE service_role;
DO $t$
DECLARE removed bigint; unresolved bigint; rows_leased bigint; did_complete boolean;
BEGIN
 SELECT deleted_count,unresolved_count INTO removed,unresolved
 FROM public.aegis_outbox_purge_expired_v1(0);
 IF removed<>0 OR unresolved<>0 THEN RAISE EXCEPTION 'ZERO BATCH MUST NOT DELETE'; END IF;
 SELECT deleted_count,unresolved_count INTO removed,unresolved
 FROM public.aegis_outbox_purge_expired_v1(1);
 IF removed<>1 OR unresolved<>1 THEN RAISE EXCEPTION 'EXPIRED SENDING ROW NOT AUDITED'; END IF;
 SELECT count(*) INTO rows_leased FROM public.aegis_outbox_claim_delivery_v1(
  repeat('c',64),repeat('d',64),'cccccccc-cccc-4ccc-8ccc-cccccccccccc');
 IF rows_leased<>1 THEN RAISE EXCEPTION 'FIRST LEASE FAILED'; END IF;
 SELECT count(*) INTO rows_leased FROM public.aegis_outbox_claim_delivery_v1(
  repeat('c',64),repeat('d',64),'dddddddd-dddd-4ddd-8ddd-dddddddddddd');
 IF rows_leased<>0 THEN RAISE EXCEPTION 'DUPLICATE LEASE ADMITTED'; END IF;
 SELECT public.aegis_outbox_complete_delivery_v1(repeat('c',64),repeat('d',64),
  'dddddddd-dddd-4ddd-8ddd-dddddddddddd',true) INTO did_complete;
 IF did_complete THEN RAISE EXCEPTION 'WRONG ATTEMPT ACKED'; END IF;
 SELECT public.aegis_outbox_complete_delivery_v1(repeat('c',64),repeat('d',64),
  'cccccccc-cccc-4ccc-8ccc-cccccccccccc',true) INTO did_complete;
 IF NOT did_complete THEN RAISE EXCEPTION 'CORRECT ATTEMPT NOT ACKED'; END IF;
END $t$;
RESET ROLE;
DO $t$
BEGIN
 IF (select count(*) from public.aegis_agent_dispatch_claims_v1)<>3 THEN
   RAISE EXCEPTION 'PAID DISPATCH CLAIMS WERE LOST'; END IF;
 IF (select count(*) from public.aegis_agent_result_outbox_v1)<>2 THEN
   RAISE EXCEPTION 'NONEXPIRED CIPHERTEXT LOST'; END IF;
END $t$;
SQL
# Independent sessions compete to lease the same remaining READY row.
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
psql -X -qAt -v ON_ERROR_STOP=1 -c "set role service_role; select count(*) from public.aegis_outbox_claim_delivery_v1(repeat('e',64),repeat('f',64),'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee');" > "$tmp/1" &
a=$!
psql -X -qAt -v ON_ERROR_STOP=1 -c "set role service_role; select count(*) from public.aegis_outbox_claim_delivery_v1(repeat('e',64),repeat('f',64),'ffffffff-ffff-4fff-8fff-ffffffffffff');" > "$tmp/2" &
b=$!
wait "$a"; wait "$b"
actual="$(cat "$tmp/1" "$tmp/2" | sort -n)"
if [ "$actual" != "$(printf '0\n1')" ]; then
  echo "DENIED: concurrent delivery lease count was $actual, expected 0/1" >&2; exit 1
fi
echo "PASS_DISPOSABLE_POSTGRES_OUTBOX: ACL, expiry, audit, paid-claim preservation, ACK, concurrent lease"
