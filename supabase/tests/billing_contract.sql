-- pgTAP contract tests (run with supabase db test).
BEGIN;
SELECT plan(14);
SELECT has_table('public','organizations','organization ledger exists');
SELECT has_table('public','subscriptions','subscription ledger exists');
SELECT has_table('public','entitlements','entitlement ledger exists');
SELECT has_table('public','billing_webhook_events','webhook idempotency ledger exists');
SELECT has_function('public','ingest_billing_event',ARRAY['text','text','text','jsonb','text','text','text','text','timestamp with time zone','timestamp with time zone','timestamp with time zone','boolean'],'replay-safe webhook transition exists');
SELECT has_function('public','authorize_api_key_usage',ARRAY['text','text','integer'],'gateway entitlement authorization exists');
SELECT has_function('public','reconcile_billing',ARRAY['text'],'reconciliation job function exists');
SELECT public.ingest_billing_event('stripe','evt-contract-create','customer.subscription.created','{}','sub-contract','billing-test@example.com','self_serve','active','2026-07-17T00:00:00Z',NULL,'2026-08-17T00:00:00Z',false) IS NOT NULL AS "created";
SELECT is((SELECT count(*)::int FROM billing_webhook_events WHERE provider='stripe' AND provider_event_id='evt-contract-create'),1,'first webhook is stored once');
SELECT is((public.ingest_billing_event('stripe','evt-contract-create','customer.subscription.created','{}','sub-contract','billing-test@example.com','self_serve','active','2026-07-17T00:00:00Z',NULL,'2026-08-17T00:00:00Z',false)->>'duplicate')::boolean,true,'duplicate webhook is a no-op');
SELECT is((public.ingest_billing_event('stripe','evt-contract-stale','customer.subscription.updated','{}','sub-contract','billing-test@example.com','evaluation','active','2026-07-16T00:00:00Z',NULL,NULL,false)->>'stale')::boolean,true,'out-of-order webhook is rejected');
SELECT is((SELECT status FROM entitlements e JOIN subscriptions s ON s.id=e.subscription_id WHERE s.provider_subscription_id='sub-contract' ORDER BY e.created_at DESC LIMIT 1),'active','stale event does not revoke entitlement');
SELECT public.ingest_billing_event('stripe','evt-contract-cancel','customer.subscription.deleted','{}','sub-contract','billing-test@example.com','self_serve','canceled','2026-07-18T00:00:00Z',NULL,NULL,false) IS NOT NULL AS "cancelled";
SELECT is((SELECT count(*)::int FROM entitlements e JOIN subscriptions s ON s.id=e.subscription_id WHERE s.provider_subscription_id='sub-contract' AND e.status='active'),0,'cancellation revokes entitlement');
SELECT * FROM finish();
ROLLBACK;
