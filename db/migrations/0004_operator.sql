-- 0004_operator
-- Operator (support) access, docs/plan/08-dashboard-and-connect-ui.md section 6.
-- Operators resolve stuck connections without database access. These SECURITY
-- DEFINER functions are the only cross-account reads, and the API calls them only
-- for principals carrying the operator flag (set by migration or break-glass CLI);
-- every use is audited.

create function control.operator_search (p_q text)
  returns table (connection_id uuid, environment_id uuid, environment_slug text, account_id uuid, account_name text,
                 organization_id uuid, organization_name text, connector_id text, state text, health_code text,
                 vendor_tenant_ref text, identifier text, created_at timestamptz)
  language sql
  stable
  security definer
  set search_path = pg_catalog, control
as $$
  select c.id, c.environment_id, e.slug, a.id, a.name, o.id, o.name, c.connector_id, c.state, c.health_code,
         c.vendor_tenant_ref, c.identifier, c.created_at
    from control.connection c
    join control.environment e on e.id = c.environment_id
    join control.account a on a.id = e.account_id
    join control.organization o on o.id = c.organization_id
   where c.id::text = p_q or c.vendor_tenant_ref = p_q or c.identifier = p_q
      or o.id::text = p_q or o.identifier = p_q or o.name ilike '%' || p_q || '%'
      or a.slug = p_q or a.name ilike '%' || p_q || '%' or a.id::text = p_q
   order by c.created_at desc
   limit 200
$$;

create function control.operator_scheduler ()
  returns table (run_id uuid, environment_id uuid, connection_id uuid, connector_id text, stream text, mode text,
                 state text, priority smallint, attempt integer, not_before timestamptz, deadline_at timestamptz,
                 health_code text, error jsonb, created_at timestamptz, waiting_reason text)
  language sql
  stable
  security definer
  set search_path = pg_catalog, sync
as $$
  select r.id, r.environment_id, r.connection_id, r.connector_id, r.stream, r.mode, r.state, r.priority, r.attempt,
         r.not_before, r.deadline_at, r.health_code, r.error, r.created_at,
         case r.state
           when 'PARKED' then 'vendor rate limit or export preparing until not_before'
           when 'RETRY_WAIT' then 'backoff after a retryable failure (attempt ' || r.attempt || ')'
           when 'QUEUED' then case when r.not_before > now() then 'not before ' || r.not_before
                                   else 'waiting for admission (priority, fairness, caps)' end
           when 'ADMITTED' then 'admitted, waiting for a worker'
           else 'running' end
    from sync.stream_run r
   where r.state in ('QUEUED', 'ADMITTED', 'RUNNING', 'PARKED', 'RETRY_WAIT')
   order by r.priority, r.created_at
   limit 1000
$$;

create function control.operator_environment (p_environment_id uuid)
  returns table (id uuid, account_id uuid, slug text, name text)
  language sql
  stable
  security definer
  set search_path = pg_catalog, control
as $$
  select e.id, e.account_id, e.slug, e.name from control.environment e
   where e.id = p_environment_id and e.deleted_at is null
$$;

revoke all on function control.operator_search(text) from public;
revoke all on function control.operator_scheduler() from public;
revoke all on function control.operator_environment(uuid) from public;
grant execute on function control.operator_search(text) to sf_api, sf_system;
grant execute on function control.operator_scheduler() to sf_api, sf_system;
grant execute on function control.operator_environment(uuid) to sf_api, sf_system;
