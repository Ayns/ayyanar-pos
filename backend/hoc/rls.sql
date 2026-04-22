-- AYY-30 — Postgres RLS policies for multi-tenant isolation.
-- This SQL is applied once during provisioning. In production,
-- run via a Django migration or Terraform.
--
-- Architecture: Tenant -> Store -> Terminal
-- Shared schema, tenant_id everywhere, enforced via RLS.

-- 1. Enable RLS on all HO Console tables
ALTER TABLE hoc_tenant ENABLE ROW LEVEL SECURITY;
ALTER TABLE hoc_store ENABLE ROW LEVEL SECURITY;
ALTER TABLE hoc_user ENABLE ROW LEVEL SECURITY;
ALTER TABLE hoc_stock_transfer ENABLE ROW LEVEL SECURITY;
ALTER TABLE hoc_reconciliation ENABLE ROW LEVEL SECURITY;
ALTER TABLE hoc_catalogue_update ENABLE ROW LEVEL SECURITY;
ALTER TABLE hoc_change_feed_cursor ENABLE ROW LEVEL SECURITY;

-- 2. Per-tenant access policy
--    Uses pg_current_user() or a custom GUC set at connection time.
--    In Django, set 'app.current_tenant' via a middleware that reads
--    the request's tenant header/cookie.

CREATE POLICY hoc_tenant_isolate ON hoc_tenant FOR ALL
    USING (id::text = current_setting('app.current_tenant')::text);

CREATE POLICY hoc_tenant_store_isolate ON hoc_store FOR ALL
    USING (tenant_id::text = current_setting('app.current_tenant')::text);

CREATE POLICY hoc_tenant_user_isolate ON hoc_user FOR ALL
    USING (tenant_id::text = current_setting('app.current_tenant')::text);

CREATE POLICY hoc_tenant_transfer_isolate ON hoc_stock_transfer FOR ALL
    USING (tenant_id::text = current_setting('app.current_tenant')::text);

CREATE POLICY hoc_tenant_recon_isolate ON hoc_reconciliation FOR ALL
    USING (tenant_id::text = current_setting('app.current_tenant')::text);

CREATE POLICY hoc_tenant_catalog_update_isolate ON hoc_catalogue_update FOR ALL
    USING (tenant_id::text = current_setting('app.current_tenant')::text);

-- Change feed cursors are shared — stores need visibility into all cursors
-- so the cloud can report sync health. Scoped by the tenant that owns the stores.
CREATE POLICY hoc_tenant_cursor_isolate ON hoc_change_feed_cursor FOR ALL
    USING (
        store_id IN (
            SELECT id::text FROM hoc_store
            WHERE tenant_id::text = current_setting('app.current_tenant')::text
        )
    );

-- 3. Super-admin bypass (tenant_admin role gets full access within their tenant)
--    This is handled at the application level via the ORM scoping.
--    RLS provides defence-in-depth for direct DB access.

-- 4. Indexes for query performance (already created via Django models)
--    Additional index for RLS lookups on tenant_id text cast
CREATE INDEX idx_hoc_store_tenant_text ON hoc_store (tenant_id::text);
CREATE INDEX idx_hoc_user_tenant_text ON hoc_user (tenant_id::text);
CREATE INDEX idx_hoc_transfer_tenant_text ON hoc_stock_transfer (tenant_id::text);
CREATE INDEX idx_hoc_recon_tenant_text ON hoc_reconciliation (tenant_id::text);
CREATE INDEX idx_hoc_catalog_tenant_text ON hoc_catalogue_update (tenant_id::text);
