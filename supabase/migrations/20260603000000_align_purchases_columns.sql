-- Align purchases table column names with ls-webhook and issue-token edge functions.
--
-- Both functions consistently use ls_-prefixed column names and customer_email.
-- The initial migration (20260527000000) used shorter names that do not match.
-- This migration renames the columns and adds ls_product_id.
--
-- Renaming preserves: NOT NULL constraints, unique constraints, check constraints,
-- existing indexes (Postgres renames them automatically for constraint indexes).
-- The email index is manually recreated on the new column name.

ALTER TABLE purchases RENAME COLUMN email      TO customer_email;
ALTER TABLE purchases RENAME COLUMN order_id   TO ls_order_id;
ALTER TABLE purchases RENAME COLUMN variant_id TO ls_variant_id;

ALTER TABLE purchases ADD COLUMN IF NOT EXISTS ls_product_id text;

-- Recreate email index on the renamed column.
DROP INDEX IF EXISTS purchases_email_idx;
CREATE INDEX IF NOT EXISTS purchases_customer_email_idx ON purchases (customer_email);
