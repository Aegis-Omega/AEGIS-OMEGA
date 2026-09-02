-- Canonical billing ledger. Stripe is the source of record; other providers may
-- enter this ledger only after a verified event has been mapped to these states.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.organizations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), slug text UNIQUE NOT NULL,
  name text NOT NULL, billing_email text, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.billing_users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), auth_user_id uuid UNIQUE REFERENCES auth.users(id) ON DELETE SET NULL,
  email text UNIQUE NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.organization_users (
  organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES public.billing_users(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('owner','admin','member','billing')), created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, user_id)
);
CREATE TABLE IF NOT EXISTS public.plans (
  id text PRIMARY KEY, name text NOT NULL, kind text NOT NULL CHECK (kind IN ('free','self_serve','enterprise')),
  currency text NOT NULL DEFAULT 'usd', unit_amount_cents integer, interval text CHECK (interval IN ('month','year')),
  limits jsonb NOT NULL, provider_price_ids jsonb NOT NULL DEFAULT '{}'::jsonb, active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO public.plans (id,name,kind,unit_amount_cents,interval,limits) VALUES
 ('evaluation','Evaluation','free',0,'month','{"requests_per_period": 25, "max_api_keys": 1, "seats": 1}'::jsonb),
 ('self_serve','Self-serve','self_serve',4900,'month','{"requests_per_period": 10000, "max_api_keys": 5, "seats": 5}'::jsonb),
 ('enterprise','Enterprise contract','enterprise',NULL,'year','{"requests_per_period": -1, "max_api_keys": -1, "seats": -1, "organization_controls": true, "committed_spend_cents": 0}'::jsonb)
ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, kind=EXCLUDED.kind, limits=EXCLUDED.limits;

CREATE TABLE IF NOT EXISTS public.subscriptions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), organization_id uuid NOT NULL REFERENCES public.organizations(id), plan_id text NOT NULL REFERENCES public.plans(id),
 provider text NOT NULL CHECK(provider IN ('stripe','paypal','github_sponsors','manual')), provider_subscription_id text NOT NULL,
 provider_customer_id text, status text NOT NULL CHECK(status IN ('trialing','active','past_due','canceling','canceled','unpaid','refunded','disputed','expired')),
 current_period_start timestamptz, current_period_end timestamptz, cancel_at_period_end boolean NOT NULL DEFAULT false,
 committed_spend_cents bigint, last_provider_event_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(provider, provider_subscription_id)
);
CREATE TABLE IF NOT EXISTS public.entitlements (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
 subscription_id uuid REFERENCES public.subscriptions(id) ON DELETE CASCADE, plan_id text NOT NULL REFERENCES public.plans(id),
 status text NOT NULL CHECK(status IN ('active','revoked','expired')), starts_at timestamptz NOT NULL DEFAULT now(), ends_at timestamptz,
 limits jsonb NOT NULL, source text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), revoked_at timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_entitlement_per_subscription ON public.entitlements(subscription_id) WHERE status='active';
CREATE INDEX IF NOT EXISTS active_entitlements_org ON public.entitlements(organization_id) WHERE status='active';
CREATE TABLE IF NOT EXISTS public.api_keys (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
 key_hash text UNIQUE NOT NULL, name text NOT NULL DEFAULT 'default', revoked_at timestamptz, last_used_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE OR REPLACE FUNCTION public.issue_billing_api_key(p_organization_id uuid, p_name text DEFAULT 'default')
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,extensions AS $$
DECLARE raw_key text; key_hash text;
BEGIN
 IF NOT EXISTS (SELECT 1 FROM entitlements WHERE organization_id=p_organization_id AND status='active' AND starts_at<=now() AND (ends_at IS NULL OR ends_at>now())) THEN RAISE EXCEPTION 'organization has no active entitlement'; END IF;
 raw_key := 'aegis_' || translate(encode(extensions.gen_random_bytes(24),'base64'),'/+=','_-'); key_hash := encode(digest(raw_key,'sha256'),'hex');
 INSERT INTO api_keys(organization_id,key_hash,name) VALUES(p_organization_id,key_hash,p_name); RETURN raw_key;
END $$;
CREATE TABLE IF NOT EXISTS public.usage_periods (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), organization_id uuid NOT NULL REFERENCES public.organizations(id), entitlement_id uuid NOT NULL REFERENCES public.entitlements(id),
 starts_at timestamptz NOT NULL, ends_at timestamptz NOT NULL, request_count bigint NOT NULL DEFAULT 0, UNIQUE(entitlement_id, starts_at)
);
CREATE TABLE IF NOT EXISTS public.usage_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), organization_id uuid NOT NULL REFERENCES public.organizations(id), api_key_id uuid REFERENCES public.api_keys(id),
 usage_period_id uuid REFERENCES public.usage_periods(id), idempotency_key text NOT NULL, quantity integer NOT NULL DEFAULT 1 CHECK(quantity > 0), event_at timestamptz NOT NULL DEFAULT now(), metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
 UNIQUE(organization_id, idempotency_key)
);
CREATE TABLE IF NOT EXISTS public.invoices (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), subscription_id uuid REFERENCES public.subscriptions(id), provider text NOT NULL, provider_invoice_id text NOT NULL,
 status text NOT NULL, amount_due_cents bigint NOT NULL DEFAULT 0, amount_paid_cents bigint NOT NULL DEFAULT 0, currency text NOT NULL DEFAULT 'usd', due_at timestamptz, paid_at timestamptz, metadata jsonb NOT NULL DEFAULT '{}'::jsonb, UNIQUE(provider,provider_invoice_id)
);
CREATE TABLE IF NOT EXISTS public.billing_webhook_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), provider text NOT NULL, provider_event_id text NOT NULL, event_type text NOT NULL, payload jsonb NOT NULL,
 signature_verified boolean NOT NULL, received_at timestamptz NOT NULL DEFAULT now(), processed_at timestamptz, processing_error text, UNIQUE(provider,provider_event_id)
);
CREATE TABLE IF NOT EXISTS public.billing_audit_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), organization_id uuid REFERENCES public.organizations(id), subscription_id uuid REFERENCES public.subscriptions(id),
 event_type text NOT NULL, actor text NOT NULL DEFAULT 'billing-system', provider_event_id text, details jsonb NOT NULL DEFAULT '{}'::jsonb, occurred_at timestamptz NOT NULL DEFAULT now()
);

-- Applies a verified provider event exactly once. A stale event is retained for
-- audit, but cannot overwrite newer subscription state (replay/out-of-order safe).
CREATE OR REPLACE FUNCTION public.ingest_billing_event(p_provider text,p_event_id text,p_event_type text,p_payload jsonb,p_subscription_id text,p_customer_email text,p_plan_id text,p_status text,p_effective_at timestamptz DEFAULT now(),p_period_start timestamptz DEFAULT NULL,p_period_end timestamptz DEFAULT NULL,p_cancel_at_period_end boolean DEFAULT false)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public AS $$
DECLARE v_org uuid; v_sub subscriptions%ROWTYPE; v_inserted boolean; v_limits jsonb;
BEGIN
 INSERT INTO billing_webhook_events(provider,provider_event_id,event_type,payload,signature_verified) VALUES(p_provider,p_event_id,p_event_type,p_payload,true) ON CONFLICT(provider,provider_event_id) DO NOTHING RETURNING true INTO v_inserted;
 IF NOT COALESCE(v_inserted,false) THEN RETURN jsonb_build_object('duplicate',true); END IF;
 IF p_subscription_id IS NULL OR p_subscription_id='' THEN UPDATE billing_webhook_events SET processed_at=now() WHERE provider=p_provider AND provider_event_id=p_event_id; RETURN jsonb_build_object('stored',true); END IF;
 INSERT INTO organizations(slug,name,billing_email) VALUES ('billing-'||substr(encode(digest(lower(coalesce(p_customer_email,p_subscription_id)),'sha256'),'hex'),1,24),coalesce(p_customer_email,p_subscription_id),lower(p_customer_email)) ON CONFLICT(slug) DO UPDATE SET billing_email=coalesce(EXCLUDED.billing_email,organizations.billing_email) RETURNING id INTO v_org;
 SELECT * INTO v_sub FROM subscriptions WHERE provider=p_provider AND provider_subscription_id=p_subscription_id FOR UPDATE;
 IF FOUND AND v_sub.last_provider_event_at IS NOT NULL AND p_effective_at < v_sub.last_provider_event_at THEN UPDATE billing_webhook_events SET processed_at=now() WHERE provider=p_provider AND provider_event_id=p_event_id; INSERT INTO billing_audit_events(organization_id,subscription_id,event_type,provider_event_id,details) VALUES(v_sub.organization_id,v_sub.id,'billing.event_ignored_stale',p_event_id,jsonb_build_object('event_type',p_event_type)); RETURN jsonb_build_object('stale',true); END IF;
 SELECT limits INTO v_limits FROM plans WHERE id=p_plan_id; IF v_limits IS NULL THEN RAISE EXCEPTION 'unknown billing plan: %',p_plan_id; END IF;
 INSERT INTO subscriptions(organization_id,plan_id,provider,provider_subscription_id,status,current_period_start,current_period_end,cancel_at_period_end,last_provider_event_at) VALUES(v_org,p_plan_id,p_provider,p_subscription_id,p_status,p_period_start,p_period_end,p_cancel_at_period_end,p_effective_at) ON CONFLICT(provider,provider_subscription_id) DO UPDATE SET plan_id=EXCLUDED.plan_id,status=EXCLUDED.status,current_period_start=EXCLUDED.current_period_start,current_period_end=EXCLUDED.current_period_end,cancel_at_period_end=EXCLUDED.cancel_at_period_end,last_provider_event_at=EXCLUDED.last_provider_event_at,updated_at=now() RETURNING * INTO v_sub;
 UPDATE entitlements SET status='revoked',revoked_at=now() WHERE subscription_id=v_sub.id AND status='active';
 IF p_status IN ('active','trialing','canceling') THEN INSERT INTO entitlements(organization_id,subscription_id,plan_id,status,starts_at,ends_at,limits,source) VALUES(v_org,v_sub.id,p_plan_id,'active',coalesce(p_period_start,now()),p_period_end,v_limits,p_provider); END IF;
 INSERT INTO billing_audit_events(organization_id,subscription_id,event_type,provider_event_id,details) VALUES(v_org,v_sub.id,'billing.'||p_event_type,p_event_id,jsonb_build_object('status',p_status,'plan_id',p_plan_id));
 UPDATE billing_webhook_events SET processed_at=now() WHERE provider=p_provider AND provider_event_id=p_event_id;
 RETURN jsonb_build_object('processed',true,'subscription_id',v_sub.id);
EXCEPTION WHEN OTHERS THEN UPDATE billing_webhook_events SET processing_error=SQLERRM WHERE provider=p_provider AND provider_event_id=p_event_id; RAISE;
END $$;

-- Gateway authorization and metering are one transaction. It rejects revoked,
-- expired, unpaid/disputed, or quota-exhausted entitlements before inference.
CREATE OR REPLACE FUNCTION public.authorize_api_key_usage(p_key_hash text,p_idempotency_key text,p_quantity integer DEFAULT 1)
RETURNS TABLE(customer_email text,tier text,usage_count int,usage_limit int,organization_id uuid,entitlement_id uuid) LANGUAGE plpgsql SECURITY DEFINER SET search_path=public AS $$
DECLARE k api_keys%ROWTYPE; e entitlements%ROWTYPE; period usage_periods%ROWTYPE; lim int;
BEGIN
 SELECT * INTO k FROM api_keys WHERE key_hash=p_key_hash AND revoked_at IS NULL FOR UPDATE; IF NOT FOUND THEN RETURN; END IF;
 SELECT * INTO e FROM entitlements WHERE organization_id=k.organization_id AND status='active' AND starts_at<=now() AND (ends_at IS NULL OR ends_at>now()) ORDER BY created_at DESC LIMIT 1 FOR UPDATE; IF NOT FOUND THEN RETURN; END IF;
 lim:=COALESCE((e.limits->>'requests_per_period')::int,0); INSERT INTO usage_periods(organization_id,entitlement_id,starts_at,ends_at) VALUES(k.organization_id,e.id,date_trunc('month',now()),date_trunc('month',now())+interval '1 month') ON CONFLICT(entitlement_id,starts_at) DO UPDATE SET ends_at=EXCLUDED.ends_at RETURNING * INTO period;
 IF EXISTS(SELECT 1 FROM usage_events WHERE organization_id=k.organization_id AND idempotency_key=p_idempotency_key) THEN RETURN QUERY SELECT ''::text,e.plan_id,period.request_count,lim,k.organization_id,e.id; RETURN; END IF;
 IF lim >= 0 AND period.request_count+p_quantity>lim THEN RETURN; END IF;
 INSERT INTO usage_events(organization_id,api_key_id,usage_period_id,idempotency_key,quantity) VALUES(k.organization_id,k.id,period.id,p_idempotency_key,p_quantity); UPDATE usage_periods SET request_count=request_count+p_quantity WHERE id=period.id RETURNING * INTO period; UPDATE api_keys SET last_used_at=now() WHERE id=k.id;
 RETURN QUERY SELECT ''::text,e.plan_id,period.request_count,lim,k.organization_id,e.id;
END $$;
REVOKE ALL ON FUNCTION public.ingest_billing_event(text,text,text,jsonb,text,text,text,text,timestamptz,timestamptz,timestamptz,boolean) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.authorize_api_key_usage(text,text,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.ingest_billing_event(text,text,text,jsonb,text,text,text,text,timestamptz,timestamptz,timestamptz,boolean), public.authorize_api_key_usage(text,text,integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.issue_billing_api_key(uuid,text) TO service_role;

-- Reconciliation is intentionally read-only: schedule this with pg_cron and
-- alert on returned rows rather than silently mutating Stripe-owned state.
CREATE OR REPLACE FUNCTION public.reconcile_billing(p_provider text DEFAULT 'stripe')
RETURNS TABLE(subscription_id uuid, issue text, detail jsonb) LANGUAGE sql STABLE SECURITY DEFINER SET search_path=public AS $$
 SELECT s.id, 'missing_active_entitlement', jsonb_build_object('status',s.status)
 FROM subscriptions s LEFT JOIN entitlements e ON e.subscription_id=s.id AND e.status='active'
 WHERE s.provider=p_provider AND s.status IN ('active','trialing','canceling') AND e.id IS NULL
 UNION ALL
 SELECT e.subscription_id, 'entitlement_for_inactive_subscription', jsonb_build_object('status',s.status)
 FROM entitlements e JOIN subscriptions s ON s.id=e.subscription_id
 WHERE s.provider=p_provider AND e.status='active' AND s.status NOT IN ('active','trialing','canceling');
$$;
REVOKE ALL ON FUNCTION public.reconcile_billing(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.reconcile_billing(text) TO service_role;
