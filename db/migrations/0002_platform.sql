-- 0002_platform
-- The platform schema: docs/plan/02-data-model.md.
--
--   control  accounts, users, environments, keys, organizations, connectors,
--            vendor apps, integrations, connections, credentials, connect flow
--   sync     schedules, jobs, stream runs, checkpoints, rate buckets, ingress
--   data     canonical resources and findings (hash partitioned), history, CVEs
--   events   outbox and outbound webhooks
--   obs      operation log, audit, usage
--
-- Tenant rows carry environment_id and are protected by row-level security keyed
-- on the transaction-local setting app.environment_id (set by tenant_tx). The
-- application never connects as the owner: each process does SET ROLE to one of
-- sf_api, sf_worker or sf_system (part 9, section 2).
--
-- Forward-only. The "never edit after applied" rule binds from the first real
-- deployment (part 1, section 5).

-- ---------------------------------------------------------------------------
-- Roles
-- ---------------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'sf_api') then
    create role sf_api nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'sf_worker') then
    create role sf_worker nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'sf_system') then
    create role sf_system nologin bypassrls;
  end if;
end
$$;

-- The migrating login may SET ROLE to each application role.
grant sf_api, sf_worker, sf_system to current_user;

create extension if not exists pg_trgm;

create schema if not exists control;
create schema if not exists sync;
create schema if not exists data;
create schema if not exists events;
create schema if not exists obs;

-- The tenant setting, read by every RLS policy. Null (no setting) matches nothing.
create function control.current_environment_id ()
  returns uuid
  language sql
  stable
as $$
  select nullif(current_setting('app.environment_id', true), '')::uuid
$$;

-- Creates range partitions of `p_parent` covering [p_from, p_to) by day or month,
-- plus a default partition. Idempotent. Used by the migration and by the
-- maintenance partition manager (part 9, section 3).
create function public.sf_ensure_partitions (
  p_parent regclass,
  p_unit text,
  p_from date,
  p_to date
)
  returns integer
  language plpgsql
  security definer
  set search_path = pg_catalog, public
as $$
declare
  v_schema text;
  v_table text;
  v_start date;
  v_end date;
  v_name text;
  v_created integer := 0;
begin
  if p_unit not in ('day', 'month') then
    raise exception 'unit must be day or month';
  end if;
  select n.nspname, c.relname into v_schema, v_table
    from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where c.oid = p_parent;

  v_start := case when p_unit = 'day' then p_from else date_trunc('month', p_from)::date end;
  while v_start < p_to loop
    v_end := case when p_unit = 'day' then v_start + 1 else (v_start + interval '1 month')::date end;
    v_name := v_table || '_p' || to_char(v_start, case when p_unit = 'day' then 'YYYYMMDD' else 'YYYYMM' end);
    if to_regclass(format('%I.%I', v_schema, v_name)) is null then
      execute format(
        'create table %I.%I partition of %I.%I for values from (%L) to (%L)',
        v_schema, v_name, v_schema, v_table, v_start, v_end
      );
      v_created := v_created + 1;
    end if;
    v_start := v_end;
  end loop;

  if to_regclass(format('%I.%I', v_schema, v_table || '_default')) is null then
    execute format('create table %I.%I partition of %I.%I default',
                   v_schema, v_table || '_default', v_schema, v_table);
  end if;
  return v_created;
end;
$$;

-- Drops range partitions of `p_parent` whose upper bound is at or before p_before.
create function public.sf_drop_partitions_before (p_parent regclass, p_before date)
  returns integer
  language plpgsql
  security definer
  set search_path = pg_catalog, public
as $$
declare
  r record;
  v_upper text;
  v_dropped integer := 0;
begin
  for r in
    select c.oid::regclass as part, pg_get_expr(c.relpartbound, c.oid) as bound
      from pg_inherits i join pg_class c on c.oid = i.inhrelid
     where i.inhparent = p_parent
  loop
    if r.bound = 'DEFAULT' then
      continue;
    end if;
    v_upper := substring(r.bound from 'TO \(''([^'']+)''\)');
    if v_upper is not null and v_upper::timestamptz <= p_before::timestamptz then
      execute format('drop table %s', r.part);
      v_dropped := v_dropped + 1;
    end if;
  end loop;
  return v_dropped;
end;
$$;

-- ===========================================================================
-- control
-- ===========================================================================

create table control.account (
    id                      uuid primary key default absurd.portable_uuidv7(),
    name                    text not null,
    slug                    text not null unique check (slug ~ '^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$'),
    workos_organization_id  text unique,
    plan                    text not null default 'free',
    created_at              timestamptz not null default now()
);

create table control.app_user (
    id              uuid primary key default absurd.portable_uuidv7(),
    workos_user_id  text not null unique,
    email           text not null,
    name            text,
    is_operator     boolean not null default false,
    created_at      timestamptz not null default now(),
    last_seen_at    timestamptz
);

create table control.membership (
    account_id  uuid not null references control.account (id) on delete cascade,
    user_id     uuid not null references control.app_user (id) on delete cascade,
    role        text not null check (role in ('admin', 'developer', 'support')),
    created_at  timestamptz not null default now(),
    primary key (account_id, user_id)
);

create table control.environment (
    id                         uuid primary key default absurd.portable_uuidv7(),
    account_id                 uuid not null references control.account (id) on delete cascade,
    slug                       text not null check (slug ~ '^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$'),
    name                       text not null,
    is_production              boolean not null default false,
    settings                   jsonb not null default '{}',
    vault_public_key           bytea not null,
    vault_private_key_wrapped  bytea,
    vault_key_version          integer not null default 1,
    vault_previous_public_key  bytea,
    vault_previous_private_key_wrapped bytea,
    created_at                 timestamptz not null default now(),
    deleted_at                 timestamptz
);
create unique index environment_slug_live on control.environment (account_id, slug)
    where deleted_at is null;

create table control.api_key (
    id              uuid primary key default absurd.portable_uuidv7(),
    environment_id  uuid not null references control.environment (id) on delete cascade,
    name            text not null,
    prefix          text not null,
    hash            bytea not null unique,
    scopes          text[] not null,
    created_by      uuid,
    created_at      timestamptz not null default now(),
    last_used_at    timestamptz,
    expires_at      timestamptz,
    revoked_at      timestamptz,
    check (scopes <@ array['provisioning:read', 'provisioning:write', 'data:read',
                           'jobs:execute', 'webhooks:manage', 'keys:manage',
                           'actions:write']::text[])
);
create index api_key_env on control.api_key (environment_id);

create table control.organization (
    id              uuid primary key default absurd.portable_uuidv7(),
    environment_id  uuid not null references control.environment (id) on delete cascade,
    identifier      text not null check (length(identifier) between 1 and 255),
    name            text not null check (length(name) between 1 and 255),
    metadata        jsonb not null default '{}',
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    deleted_at      timestamptz
);
create unique index organization_identifier_live on control.organization (environment_id, identifier)
    where deleted_at is null;
create index organization_name_trgm on control.organization using gin (name gin_trgm_ops);
create index organization_identifier_trgm on control.organization using gin (identifier gin_trgm_ops);

create table control.connector (
    id             text not null,
    version        text not null,
    manifest       jsonb not null,
    status         text not null check (status in ('beta', 'ga', 'deprecated')),
    is_current     boolean not null default false,
    deprecated_at  timestamptz,
    loaded_at      timestamptz not null default now(),
    primary key (id, version)
);
create unique index connector_current on control.connector (id) where is_current;

create table control.vendor_app (
    id                  uuid primary key default absurd.portable_uuidv7(),
    environment_id      uuid references control.environment (id) on delete cascade,
    connector_id        text not null,
    name                text not null,
    base_url            text not null,
    config              jsonb not null default '{}',
    secrets_sealed      bytea,
    secrets_key_version integer,
    ingress_secret_enc  bytea,
    is_default          boolean not null default false,
    created_at          timestamptz not null default now(),
    deleted_at          timestamptz
);
create index vendor_app_env on control.vendor_app (environment_id, connector_id);
-- One platform default per (connector, permission tier).
create unique index vendor_app_platform_default on control.vendor_app
    (connector_id, (config ->> 'permission_tier'))
    where environment_id is null and is_default and deleted_at is null;

-- The platform key pair (seals platform-owned vendor app secrets). Single row.
create table control.platform_key (
    id                    smallint primary key default 1 check (id = 1),
    public_key            bytea not null,
    private_key_wrapped   bytea not null,
    key_version           integer not null default 1,
    created_at            timestamptz not null default now()
);

create table control.integration (
    id                  uuid primary key default absurd.portable_uuidv7(),
    environment_id      uuid not null references control.environment (id) on delete cascade,
    connector_id        text not null,
    key                 text not null check (key ~ '^[a-z0-9](?:[a-z0-9_-]*[a-z0-9])?$'),
    display_name        text not null,
    vendor_app_id       uuid references control.vendor_app (id),
    enabled_streams     text[] not null,
    stream_intervals    jsonb not null default '{}',
    option_defaults     jsonb not null default '{}',
    write_back_enabled  boolean not null default false,
    created_at          timestamptz not null default now(),
    deleted_at          timestamptz
);
create unique index integration_key_live on control.integration (environment_id, key)
    where deleted_at is null;

create table control.connection (
    id                 uuid primary key default absurd.portable_uuidv7(),
    environment_id     uuid not null references control.environment (id) on delete cascade,
    organization_id    uuid not null references control.organization (id),
    integration_id     uuid not null references control.integration (id),
    connector_id       text not null,
    connector_version  text not null,
    identifier         text,
    state              text not null default 'PENDING'
                       check (state in ('PENDING', 'ACTIVE', 'PAUSED', 'DELETED', 'HARD_DELETED')),
    direction          text not null default 'SOURCE' check (direction in ('SOURCE', 'DESTINATION')),
    is_sandbox         boolean not null default false,
    options            jsonb not null default '{}',
    connection_config  jsonb not null default '{}',
    vendor_tenant_ref  text,
    tenant_fingerprint bytea,
    metadata           jsonb not null default '{}' check (octet_length(metadata::text) <= 16384),
    tags               jsonb not null default '{}',
    health_status      text not null default 'INITIALIZING'
                       check (health_status in ('INITIALIZING', 'HEALTHY', 'UNHEALTHY')),
    health_code        text not null default 'INITIALIZING',
    resolution_owner   text check (resolution_owner in ('PLATFORM', 'CUSTOMER', 'VENDOR')),
    health_details     jsonb not null default '[]',
    health_description text,
    health_changed_at  timestamptz,
    pending_detail     text,
    event_seq          bigint not null default 0,
    data_shard         text not null default 'primary',
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now(),
    deleted_at         timestamptz,
    purge_after        timestamptz
);
create index connection_env_org on control.connection (environment_id, organization_id);
create index connection_env_health on control.connection (environment_id, health_code);
create index connection_tenant_ref on control.connection (vendor_tenant_ref);
create index connection_tags on control.connection using gin (tags);
create unique index connection_identifier_live on control.connection (organization_id, identifier)
    where deleted_at is null and identifier is not null;
create unique index connection_fingerprint_live on control.connection
    (organization_id, integration_id, tenant_fingerprint)
    where deleted_at is null and tenant_fingerprint is not null;

create table control.credential (
    connection_id            uuid primary key references control.connection (id) on delete cascade,
    environment_id           uuid not null,
    auth_mode                text not null
                             check (auth_mode in ('APP', 'API_KEY', 'BASIC', 'OAUTH2', 'OAUTH2_CC', 'AWS_ROLE', 'NONE')),
    sealed                   bytea,
    staged_sealed            bytea,
    token_sealed             bytea,
    token_expires_at         timestamptz,
    vault_key_version        integer not null default 1,
    last_refresh_at          timestamptz,
    last_refresh_failure_at  timestamptz,
    last_refresh_fail_day    date,
    refresh_fail_days        integer not null default 0,
    refresh_exhausted        boolean not null default false,
    rotated_at               timestamptz,
    fields_set               text[] not null default '{}',
    updated_at               timestamptz not null default now()
);

create table control.connection_grant (
    connection_id   uuid not null references control.connection (id) on delete cascade,
    environment_id  uuid not null,
    stream          text not null,
    status          text not null check (status in ('GRANTED', 'UNAUTHORIZED', 'NOT_ENABLED', 'UNSUPPORTED', 'UNKNOWN')),
    endpoint        text,
    detail          text,
    checked_at      timestamptz not null default now(),
    primary key (connection_id, stream)
);

create table control.connect_session (
    id                       uuid primary key default absurd.portable_uuidv7(),
    environment_id           uuid not null references control.environment (id) on delete cascade,
    organization_id          uuid not null references control.organization (id),
    token_hash               bytea not null unique,
    allowed_integration_ids  uuid[] not null default '{}',
    connection_id            uuid,
    option_presets           jsonb not null default '{}',
    redirect_success         text,
    redirect_error           text,
    expires_at               timestamptz not null,
    used_at                  timestamptz,
    created_at               timestamptz not null default now()
);

create table control.oauth_state (
    state               text primary key,
    environment_id      uuid not null,
    connect_session_id  uuid not null references control.connect_session (id) on delete cascade,
    connection_id       uuid,
    vendor_app_id       uuid not null,
    kind                text not null default 'install' check (kind in ('install', 'authorize', 'oauth2')),
    code_verifier       text,
    -- The callback's code, sealed to the environment key until a worker consumes it.
    callback_sealed     bytea,
    callback_key_version integer,
    expires_at          timestamptz not null,
    consumed_at         timestamptz,
    created_at          timestamptz not null default now()
);

create table control.connection_health_event (
    id              uuid not null default absurd.portable_uuidv7(),
    connection_id   uuid not null,
    environment_id  uuid not null,
    from_code       text,
    to_code         text not null,
    details         jsonb not null default '[]',
    job_id          uuid,
    at              timestamptz not null default now(),
    primary key (at, id)
) partition by range (at);
create index connection_health_event_conn on control.connection_health_event (connection_id, at desc);

create table control.idempotency_key (
    environment_id  uuid not null,
    key             text not null,
    request_hash    bytea not null,
    status          integer,
    response        jsonb,
    created_at      timestamptz not null default now(),
    primary key (environment_id, key)
);

-- ===========================================================================
-- sync
-- ===========================================================================

create table sync.stream_schedule (
    id               uuid primary key default absurd.portable_uuidv7(),
    environment_id   uuid not null,
    connection_id    uuid not null references control.connection (id) on delete cascade,
    stream           text not null,
    interval_s       integer not null check (interval_s > 0),
    state            text not null default 'STARTED' check (state in ('STARTED', 'PAUSED', 'DELETED')),
    next_run_at      timestamptz not null,
    full_every_s     integer,
    next_full_at     timestamptz,
    last_success_at  timestamptz,
    last_run_id      uuid,
    unique (connection_id, stream)
);
create index stream_schedule_due on sync.stream_schedule (next_run_at) where state = 'STARTED';

create table sync.job (
    id              uuid primary key default absurd.portable_uuidv7(),
    environment_id  uuid not null,
    connection_id   uuid not null,
    type            text not null check (type in ('INITIAL', 'SCHEDULED', 'ON_DEMAND', 'WEBHOOK', 'RETRY')),
    status          text not null default 'QUEUED'
                    check (status in ('QUEUED', 'RUNNING', 'SUCCESS', 'PARTIAL', 'FAILED', 'CANCELLED')),
    requested_by    text,
    options         jsonb not null default '{}',
    health_code     text,
    failure_reason  text,
    created_at      timestamptz not null default now(),
    started_at      timestamptz,
    finished_at     timestamptz
);
create index job_connection on sync.job (connection_id, created_at desc);
create index job_open on sync.job (created_at) where status in ('QUEUED', 'RUNNING');

create sequence sync.generation_seq;

create table sync.stream_run (
    id                uuid primary key default absurd.portable_uuidv7(),
    job_id            uuid not null references sync.job (id) on delete cascade,
    environment_id    uuid not null,
    connection_id     uuid not null,
    stream            text not null,
    mode              text not null check (mode in ('backfill', 'incremental', 'full', 'targeted')),
    state             text not null default 'QUEUED'
                      check (state in ('QUEUED', 'ADMITTED', 'RUNNING', 'PARKED', 'RETRY_WAIT',
                                       'SUCCEEDED', 'FAILED', 'CANCELLED', 'EXPIRED')),
    priority          smallint not null default 2,
    fair_key          text not null,
    budget_key        text not null,
    connector_id      text not null,
    queue             text not null,
    attempt           integer not null default 1,
    slice             integer not null default 0,
    not_before        timestamptz not null default now(),
    deadline_at       timestamptz,
    absurd_task_id    uuid,
    cancel_requested  boolean not null default false,
    generation        bigint,
    added             integer not null default 0,
    updated           integer not null default 0,
    deleted           integer not null default 0,
    unchanged         integer not null default 0,
    quarantined       integer not null default 0,
    pages             integer not null default 0,
    vendor_requests   integer not null default 0,
    health_code       text,
    warning           text,
    error             jsonb,
    target_keys       text[],
    created_at        timestamptz not null default now(),
    admitted_at       timestamptz,
    started_at        timestamptz,
    finished_at       timestamptz
);
create unique index stream_run_one_active on sync.stream_run (connection_id, stream)
    where state in ('QUEUED', 'ADMITTED', 'RUNNING', 'PARKED', 'RETRY_WAIT') and mode <> 'targeted';
create index stream_run_admission on sync.stream_run (priority, not_before, created_at)
    where state in ('QUEUED', 'PARKED', 'RETRY_WAIT');
create index stream_run_budget_active on sync.stream_run (budget_key)
    where state in ('ADMITTED', 'RUNNING');
create index stream_run_env_active on sync.stream_run (environment_id)
    where state in ('ADMITTED', 'RUNNING');
create index stream_run_job on sync.stream_run (job_id);
create index stream_run_conn on sync.stream_run (connection_id, created_at desc);

create table sync.checkpoint (
    connection_id   uuid not null,
    stream          text not null,
    key             text not null check (key in ('default', 'sweep', 'export')),
    environment_id  uuid not null,
    value           jsonb not null,
    version         integer not null default 1,
    updated_at      timestamptz not null default now(),
    primary key (connection_id, stream, key)
);

create table sync.concurrency_limit (
    scope_kind   text not null check (scope_kind in ('global', 'environment', 'connector', 'budget', 'connection', 'queue')),
    scope_id     text not null,
    max_running  integer not null check (max_running >= 0),
    primary key (scope_kind, scope_id)
);

create table sync.rate_bucket (
    key               text primary key,
    capacity          double precision not null,
    tokens            double precision not null,
    refill_per_s      double precision not null,
    reset_at          timestamptz,
    vendor_remaining  integer,
    vendor_limit      integer,
    minute_capacity   double precision,
    minute_tokens     double precision,
    minute_reset_at   timestamptz,
    updated_at        timestamptz not null default now()
);

-- Not range-partitioned (a deliberate deviation from part 2): the unique
-- (vendor_app_id, delivery_id) must hold across day boundaries, and a
-- partitioned unique index would need the partition key. Retention is a daily
-- delete of rows older than 7 days instead of a partition drop.
create table sync.ingress_delivery (
    id                 uuid primary key default absurd.portable_uuidv7(),
    vendor_app_id      uuid not null,
    connector_id       text not null,
    delivery_id        text not null,
    event              text not null,
    action             text,
    vendor_tenant_ref  text,
    payload            jsonb not null,
    status             text not null default 'RECEIVED' check (status in ('RECEIVED', 'ROUTED', 'IGNORED', 'FAILED')),
    detail             text,
    received_at        timestamptz not null default now(),
    processed_at       timestamptz,
    unique (vendor_app_id, delivery_id)
);
create index ingress_delivery_received on sync.ingress_delivery (received_at);
create index ingress_delivery_pending on sync.ingress_delivery (received_at) where status = 'RECEIVED';

create table sync.dirty_record (
    connection_id   uuid not null,
    stream          text not null,
    vendor_key      text not null,
    environment_id  uuid not null,
    reason          text,
    enqueued_at     timestamptz not null default now(),
    primary key (connection_id, stream, vendor_key)
);

create table sync.raw_page (
    id               uuid not null default absurd.portable_uuidv7(),
    environment_id   uuid not null,
    connection_id    uuid not null,
    stream           text not null,
    stream_run_id    uuid,
    seq              integer not null,
    blob_key         text not null,
    bytes            integer not null,
    request_summary  jsonb not null default '{}',
    created_at       timestamptz not null default now(),
    expires_at       timestamptz not null,
    primary key (created_at, id)
) partition by range (created_at);
create index raw_page_run on sync.raw_page (stream_run_id, seq);
create index raw_page_conn on sync.raw_page (connection_id, stream, created_at);

create table sync.scheduler_lease (
    name        text primary key,
    holder      text not null,
    expires_at  timestamptz not null
);

-- ===========================================================================
-- data
-- ===========================================================================

create table data.resource (
    id               uuid not null,
    environment_id   uuid not null,
    organization_id  uuid not null,
    connection_id    uuid not null,
    stream           text not null,
    natural_key      text not null check (length(natural_key) <= 512),
    type             text not null check (type in ('BRANCH', 'HOST', 'CONTAINER', 'DEPENDENCY', 'IMAGE',
                     'REPOSITORY', 'VENDOR', 'KUBERNETES', 'FUNCTION', 'SOFTWARE', 'UNKNOWN')),
    state            text not null check (state in ('ACTIVE', 'IGNORED', 'DELETED', 'INACTIVE', 'QUARANTINED', 'UNKNOWN')),
    name             text,
    url              text,
    groups           jsonb not null default '[]',
    tags             jsonb not null default '[]',
    data             jsonb not null default '{}',
    cloud_metadata   jsonb,
    vendor_id        text,
    vendor_attributes_data jsonb not null default '{}',
    vendor_data      bytea,
    is_stub          boolean not null default false,
    entity_id        uuid,
    meta_derived     text[] not null default '{}',
    connector_version text,
    hash             bytea,
    seen_gen         bigint not null default 0,
    first_seen_at    timestamptz not null,
    last_seen_at     timestamptz not null,
    created_at       timestamptz not null,
    updated_at       timestamptz not null,
    deleted_at       timestamptz,
    primary key (connection_id, id),
    unique (connection_id, natural_key)
) partition by hash (connection_id);
create index resource_updated on data.resource (connection_id, updated_at, id);
create index resource_type_state on data.resource (connection_id, type, state);
create index resource_id on data.resource (id);
create index resource_org_updated on data.resource (organization_id, updated_at, id);

create table data.vulnerability_finding (
    id                  uuid not null,
    environment_id      uuid not null,
    organization_id     uuid not null,
    connection_id       uuid not null,
    stream              text not null,
    natural_key         text not null check (length(natural_key) <= 512),
    type                text not null check (type in ('DEPENDENCY', 'CODE', 'SECRET', 'CONTAINER', 'IAC',
                        'HOST', 'DOMAIN', 'UNKNOWN')),
    title               text,
    description         text,
    severity            text not null check (severity in ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO', 'UNKNOWN')),
    severity_rank       smallint not null,
    state               text not null check (state in ('OPEN', 'CLOSED', 'REOPENED', 'IGNORED', 'DELETED', 'UNKNOWN')),
    state_updated_at    timestamptz,
    has_fix             boolean,
    exploitable         boolean,
    reachability        text check (reachability in ('REACHABLE', 'POTENTIALLY_REACHABLE', 'UNREACHABLE', 'UNKNOWN')),
    remediation         jsonb,
    analytic            jsonb,
    analytic_output     jsonb,
    product             jsonb,
    ticket              jsonb,
    resource_related    jsonb,
    vulnerabilities     jsonb not null default '[]',
    cve_ids             text[] not null default '{}',
    enrichment          jsonb,
    meta_derived        text[] not null default '{}',
    vendor_id           text,
    vendor_url          text,
    vendor_severity     text,
    vendor_state        text,
    vendor_created_at   timestamptz,
    vendor_updated_at   timestamptz,
    vendor_identifiers  jsonb,
    vendor_attributes_data jsonb,
    vendor_data         bytea,
    cluster_id          uuid,
    connector_version   text,
    hash                bytea,
    seen_gen            bigint not null default 0,
    first_seen_at       timestamptz not null,
    last_seen_at        timestamptz not null,
    created_at          timestamptz not null,
    updated_at          timestamptz not null,
    deleted_at          timestamptz,
    primary key (connection_id, id),
    unique (connection_id, natural_key)
) partition by hash (connection_id);
create index finding_updated on data.vulnerability_finding (connection_id, updated_at, id);
create index finding_state_sev on data.vulnerability_finding (connection_id, state, severity_rank desc, id);
create index finding_state_updated on data.vulnerability_finding (connection_id, state_updated_at, id);
create index finding_first_seen on data.vulnerability_finding (connection_id, first_seen_at, id);
create index finding_id on data.vulnerability_finding (id);
create index finding_org_updated on data.vulnerability_finding (organization_id, updated_at, id);
create index finding_cves on data.vulnerability_finding using gin (cve_ids);

create table data.finding_resource (
    connection_id   uuid not null,
    finding_id      uuid not null,
    resource_id     uuid not null,
    environment_id  uuid not null,
    role            text not null check (role in ('primary', 'related')),
    primary key (connection_id, finding_id, resource_id)
) partition by hash (connection_id);
create index finding_resource_res on data.finding_resource (connection_id, resource_id);

do $$
declare
  i integer;
begin
  for i in 0..63 loop
    execute format('create table data.resource_h%s partition of data.resource for values with (modulus 64, remainder %s)', lpad(i::text, 2, '0'), i);
    execute format('create table data.vulnerability_finding_h%s partition of data.vulnerability_finding for values with (modulus 64, remainder %s)', lpad(i::text, 2, '0'), i);
    execute format('create table data.finding_resource_h%s partition of data.finding_resource for values with (modulus 64, remainder %s)', lpad(i::text, 2, '0'), i);
  end loop;
end
$$;

create table data.state_history (
    id              uuid not null default absurd.portable_uuidv7(),
    environment_id  uuid not null,
    connection_id   uuid not null,
    record_id       uuid not null,
    object_type     text not null check (object_type in ('resource', 'vulnerability_finding')),
    from_state      text,
    to_state        text not null,
    at              timestamptz not null,
    source          text not null check (source in ('vendor', 'platform', 'sweep')),
    stream_run_id   uuid,
    primary key (at, id)
) partition by range (at);
create index state_history_record on data.state_history (connection_id, record_id, at);

create table data.quarantine (
    id              uuid primary key default absurd.portable_uuidv7(),
    environment_id  uuid not null,
    connection_id   uuid not null,
    stream          text not null,
    stream_run_id   uuid,
    natural_key     text,
    errors          jsonb not null,
    raw_page_id     uuid,
    created_at      timestamptz not null default now()
);
create index quarantine_conn on data.quarantine (connection_id, created_at desc);

create table data.stream_head (
    connection_id    uuid not null,
    stream           text not null,
    environment_id   uuid not null,
    object_type      text not null check (object_type in ('resource', 'vulnerability_finding')),
    live_count       bigint not null default 0,
    deleted_count    bigint not null default 0,
    bytes            bigint not null default 0,
    head_updated_at  timestamptz,
    last_generation  bigint,
    primary key (connection_id, stream)
);

-- The per (connection, object type) monotonic clock (PD-6). Separate from
-- stream_head because two streams can write the same object type.
create table data.object_clock (
    connection_id    uuid not null,
    object_type      text not null,
    environment_id   uuid not null,
    head_updated_at  timestamptz not null,
    primary key (connection_id, object_type)
);

create table data.cve (
    cve_id              text primary key,
    description         text,
    cvss                jsonb,
    cwe                 text[] not null default '{}',
    "references"        jsonb,
    published_at        timestamptz,
    modified_at         timestamptz,
    kev                 jsonb,
    epss                jsonb,
    source_modified_at  timestamptz,
    updated_at          timestamptz not null default now()
);

create table data.advisory_alias (
    alias    text primary key,
    cve_id   text not null,
    source   text not null
);
create index advisory_alias_cve on data.advisory_alias (cve_id);

create table data.enrichment_cursor (
    source      text primary key,
    value       jsonb not null,
    updated_at  timestamptz not null default now()
);

-- ===========================================================================
-- events
-- ===========================================================================

create table events.outbox_event (
    id               uuid not null default absurd.portable_uuidv7(),
    environment_id   uuid not null,
    organization_id  uuid,
    connection_id    uuid,
    sequence         bigint,
    type             text not null,
    payload          jsonb not null,
    created_at       timestamptz not null default now(),
    dispatched_at    timestamptz,
    primary key (created_at, id)
) partition by range (created_at);
create index outbox_undispatched on events.outbox_event (id) where dispatched_at is null;
create index outbox_env_id on events.outbox_event (environment_id, id);

create table events.webhook_endpoint (
    id                          uuid primary key default absurd.portable_uuidv7(),
    environment_id              uuid not null references control.environment (id) on delete cascade,
    url                         text not null check (length(url) <= 2048),
    description                 text,
    event_types                 text[] not null default '{}',
    secret_sealed               bytea not null,
    secret_key_version          integer not null default 1,
    secret_hint                 text,
    previous_secret_sealed      bytea,
    previous_secret_expires_at  timestamptz,
    enabled                     boolean not null default true,
    disabled_reason             text,
    failing_since               timestamptz,
    created_at                  timestamptz not null default now(),
    deleted_at                  timestamptz
);
create index webhook_endpoint_env on events.webhook_endpoint (environment_id) where deleted_at is null;

create function events.enforce_endpoint_limit ()
  returns trigger
  language plpgsql
as $$
begin
  if (select count(*) from events.webhook_endpoint
       where environment_id = new.environment_id and deleted_at is null and id <> new.id) >= 5 then
    raise exception 'webhook endpoint limit reached' using errcode = 'check_violation';
  end if;
  return new;
end;
$$;
create trigger webhook_endpoint_limit before insert on events.webhook_endpoint
  for each row execute function events.enforce_endpoint_limit();

create table events.webhook_delivery (
    id                uuid primary key default absurd.portable_uuidv7(),
    environment_id    uuid not null,
    event_id          uuid not null,
    endpoint_id       uuid not null references events.webhook_endpoint (id) on delete cascade,
    event_type        text not null,
    status            text not null default 'PENDING' check (status in ('PENDING', 'DELIVERED', 'FAILED', 'DEAD')),
    attempts          integer not null default 0,
    next_attempt_at   timestamptz,
    last_status_code  integer,
    last_latency_ms   integer,
    last_error        text,
    created_at        timestamptz not null default now(),
    delivered_at      timestamptz,
    unique (event_id, endpoint_id)
);
create index webhook_delivery_endpoint on events.webhook_delivery (endpoint_id, created_at desc);

create table events.webhook_attempt (
    id                uuid primary key default absurd.portable_uuidv7(),
    delivery_id       uuid not null references events.webhook_delivery (id) on delete cascade,
    environment_id    uuid not null,
    attempt           integer not null,
    at                timestamptz not null default now(),
    status_code       integer,
    latency_ms        integer,
    response_excerpt  text,
    error             text
);
create index webhook_attempt_delivery on events.webhook_attempt (delivery_id, attempt);

-- ===========================================================================
-- obs
-- ===========================================================================

create table obs.operation (
    id               uuid not null default absurd.portable_uuidv7(),
    environment_id   uuid not null,
    connection_id    uuid,
    organization_id  uuid,
    kind             text not null check (kind in ('sync', 'auth', 'action', 'webhook_in', 'webhook_out', 'passthrough')),
    action           text not null,
    status           text not null check (status in ('running', 'success', 'failed', 'warning', 'cancelled')),
    job_id           uuid,
    stream_run_id    uuid,
    request_id       text,
    started_at       timestamptz not null default now(),
    duration_ms      integer,
    summary          jsonb not null default '{}',
    primary key (started_at, id)
) partition by range (started_at);
create index operation_env on obs.operation (environment_id, started_at desc);
create index operation_conn on obs.operation (connection_id, started_at desc);
create index operation_run on obs.operation (stream_run_id);
create index operation_id on obs.operation (id);

create table obs.operation_event (
    id              uuid not null default absurd.portable_uuidv7(),
    operation_id    uuid not null,
    environment_id  uuid not null,
    at              timestamptz not null default now(),
    level           text not null check (level in ('debug', 'info', 'warning', 'error')),
    kind            text not null check (kind in ('http', 'log')),
    message         text not null,
    http            jsonb,
    primary key (at, id)
) partition by range (at);
create index operation_event_op on obs.operation_event (operation_id, at);

create table obs.audit_event (
    id              uuid not null default absurd.portable_uuidv7(),
    environment_id  uuid,
    account_id      uuid,
    actor_kind      text not null check (actor_kind in ('user', 'api_key', 'support', 'system', 'connect_session')),
    actor_id        text,
    action          text not null,
    target_kind     text,
    target_id       text,
    ip              text,
    user_agent      text,
    request_id      text,
    detail          jsonb not null default '{}',
    at              timestamptz not null default now(),
    primary key (at, id)
) partition by range (at);
create index audit_event_env on obs.audit_event (environment_id, at desc);
create index audit_event_account on obs.audit_event (account_id, at desc);

create table obs.usage_event (
    id              uuid not null default absurd.portable_uuidv7(),
    environment_id  uuid not null,
    kind            text not null,
    quantity        bigint not null default 1,
    detail          jsonb not null default '{}',
    at              timestamptz not null default now(),
    primary key (at, id)
) partition by range (at);
create index usage_event_env on obs.usage_event (environment_id, at);

create table obs.usage_daily (
    environment_id      uuid not null,
    day                 date not null,
    active_connections  integer not null default 0,
    records_stored      bigint not null default 0,
    api_calls           bigint not null default 0,
    jobs                integer not null default 0,
    records_written     bigint not null default 0,
    primary key (environment_id, day)
);

create table obs.api_rate_counter (
    environment_id  uuid not null,
    window_start    timestamptz not null,
    count           integer not null default 0,
    primary key (environment_id, window_start)
);

-- Worker liveness for `make status` and the status endpoint.
create table obs.worker_heartbeat (
    worker_id     text primary key,
    role          text not null,
    queues        text[] not null default '{}',
    hostname      text not null,
    pid           integer not null,
    version       text not null,
    concurrency   integer not null,
    started_at    timestamptz not null,
    last_seen_at  timestamptz not null
);

create table obs.alert (
    id           uuid primary key default absurd.portable_uuidv7(),
    name         text not null,
    severity     text not null check (severity in ('page', 'ticket', 'info')),
    subject      text,
    detail       jsonb not null default '{}',
    runbook      text,
    raised_at    timestamptz not null default now(),
    resolved_at  timestamptz
);
create unique index alert_open on obs.alert (name, coalesce(subject, '')) where resolved_at is null;

-- Initial range partitions: one month back, two ahead. The partition manager
-- (maintenance queue) keeps the window rolling.
select public.sf_ensure_partitions('control.connection_health_event', 'month', (current_date - 31), (current_date + 62));
select public.sf_ensure_partitions('sync.raw_page', 'day', (current_date - 2), (current_date + 8));
select public.sf_ensure_partitions('data.state_history', 'month', (current_date - 31), (current_date + 62));
select public.sf_ensure_partitions('events.outbox_event', 'month', (current_date - 31), (current_date + 62));
select public.sf_ensure_partitions('obs.operation', 'day', (current_date - 2), (current_date + 8));
select public.sf_ensure_partitions('obs.operation_event', 'day', (current_date - 2), (current_date + 8));
select public.sf_ensure_partitions('obs.audit_event', 'month', (current_date - 31), (current_date + 62));
select public.sf_ensure_partitions('obs.usage_event', 'month', (current_date - 31), (current_date + 62));

-- ===========================================================================
-- Row-level security
-- ===========================================================================
do $$
declare
  t text;
begin
  foreach t in array array[
    'control.api_key', 'control.organization', 'control.integration', 'control.connection',
    'control.credential', 'control.connection_grant', 'control.connect_session',
    'control.oauth_state', 'control.connection_health_event', 'control.idempotency_key',
    'sync.stream_schedule', 'sync.job', 'sync.stream_run', 'sync.checkpoint',
    'sync.dirty_record', 'sync.raw_page',
    'data.resource', 'data.vulnerability_finding', 'data.finding_resource',
    'data.state_history', 'data.quarantine', 'data.stream_head', 'data.object_clock',
    'events.outbox_event', 'events.webhook_endpoint', 'events.webhook_delivery',
    'events.webhook_attempt',
    'obs.operation', 'obs.operation_event', 'obs.usage_event', 'obs.usage_daily'
  ] loop
    execute format('alter table %s enable row level security', t);
    execute format(
      'create policy tenant_isolation on %s using (environment_id = control.current_environment_id()) '
      'with check (environment_id = control.current_environment_id())', t);
  end loop;
end
$$;

-- An environment row is visible to its own tenant transaction.
alter table control.environment enable row level security;
create policy tenant_isolation on control.environment
  using (id = control.current_environment_id())
  with check (id = control.current_environment_id());

-- Platform-owned apps (environment_id null) are readable by every tenant and
-- writable only by sf_system (which bypasses RLS).
alter table control.vendor_app enable row level security;
create policy tenant_read on control.vendor_app for select
  using (environment_id is null or environment_id = control.current_environment_id());
create policy tenant_write on control.vendor_app for insert
  with check (environment_id = control.current_environment_id());
create policy tenant_update on control.vendor_app for update
  using (environment_id = control.current_environment_id())
  with check (environment_id = control.current_environment_id());
create policy tenant_delete on control.vendor_app for delete
  using (environment_id = control.current_environment_id());

-- Audit rows: a tenant sees its environment's rows; inserts are always allowed
-- (account-level events have no environment).
alter table obs.audit_event enable row level security;
create policy tenant_read on obs.audit_event for select
  using (environment_id = control.current_environment_id());
create policy any_insert on obs.audit_event for insert with check (true);

-- ===========================================================================
-- Pre-tenant resolvers
-- ===========================================================================
-- Authentication must find a key or session token before it knows the tenant.
-- These SECURITY DEFINER functions are the only cross-tenant reads the API role
-- has, and each returns exactly one row for one exact secret hash.

create function control.resolve_api_key (p_hash bytea)
  returns table (id uuid, environment_id uuid, account_id uuid, scopes text[], name text,
                 expires_at timestamptz, revoked_at timestamptz, is_production boolean)
  language sql
  stable
  security definer
  set search_path = pg_catalog, control
as $$
  select k.id, k.environment_id, e.account_id, k.scopes, k.name, k.expires_at, k.revoked_at,
         e.is_production
    from control.api_key k
    join control.environment e on e.id = k.environment_id
   where k.hash = p_hash and e.deleted_at is null
$$;

create function control.resolve_connect_session (p_hash bytea)
  returns table (id uuid, environment_id uuid, organization_id uuid, account_id uuid,
                 expires_at timestamptz, used_at timestamptz)
  language sql
  stable
  security definer
  set search_path = pg_catalog, control
as $$
  select s.id, s.environment_id, s.organization_id, e.account_id, s.expires_at, s.used_at
    from control.connect_session s
    join control.environment e on e.id = s.environment_id
   where s.token_hash = p_hash and e.deleted_at is null
$$;

-- The environments of one account (session principals pick one by slug).
create function control.account_environments (p_account_id uuid)
  returns table (id uuid, account_id uuid, slug text, name text, is_production boolean,
                 settings jsonb, created_at timestamptz)
  language sql
  stable
  security definer
  set search_path = pg_catalog, control
as $$
  select e.id, e.account_id, e.slug, e.name, e.is_production, e.settings, e.created_at
    from control.environment e
   where e.account_id = p_account_id and e.deleted_at is null
   order by e.created_at
$$;

-- The OAuth callback arrives with only `state`; it resolves the tenant from it.
create function control.resolve_oauth_state (p_state text)
  returns table (state text, environment_id uuid, connect_session_id uuid, connection_id uuid,
                 vendor_app_id uuid, kind text, code_verifier text, expires_at timestamptz,
                 consumed_at timestamptz)
  language sql
  stable
  security definer
  set search_path = pg_catalog, control
as $$
  select o.state, o.environment_id, o.connect_session_id, o.connection_id, o.vendor_app_id,
         o.kind, o.code_verifier, o.expires_at, o.consumed_at
    from control.oauth_state o
   where o.state = p_state
$$;

-- Inbound webhooks name their vendor app in the URL; the API needs that one app's
-- encrypted webhook secret (or every platform app's, for the shared default).
create function control.vendor_app_ingress (p_connector text, p_ref text)
  returns table (id uuid, environment_id uuid, ingress_secret_enc bytea)
  language sql
  stable
  security definer
  set search_path = pg_catalog, control
as $$
  select a.id, a.environment_id, a.ingress_secret_enc
    from control.vendor_app a
   where a.connector_id = p_connector and a.deleted_at is null
     and ((p_ref = 'default' and a.environment_id is null)
          or a.id = (case when p_ref ~ '^[0-9a-f-]{36}$' then p_ref::uuid end))
$$;
revoke all on function control.vendor_app_ingress(text, text) from public;
grant execute on function control.vendor_app_ingress(text, text) to sf_api, sf_worker, sf_system;

-- Partition DDL runs as the owner; only the maintenance role may call it.
revoke all on function public.sf_ensure_partitions(regclass, text, date, date) from public;
revoke all on function public.sf_drop_partitions_before(regclass, date) from public;
grant execute on function public.sf_ensure_partitions(regclass, text, date, date) to sf_system;
grant execute on function public.sf_drop_partitions_before(regclass, date) to sf_system;

revoke all on function control.resolve_api_key(bytea) from public;
revoke all on function control.resolve_connect_session(bytea) from public;
revoke all on function control.account_environments(uuid) from public;
revoke all on function control.resolve_oauth_state(text) from public;
grant execute on function control.resolve_api_key(bytea) to sf_api, sf_worker, sf_system;
grant execute on function control.resolve_connect_session(bytea) to sf_api, sf_worker, sf_system;
grant execute on function control.account_environments(uuid) to sf_api, sf_worker, sf_system;
grant execute on function control.resolve_oauth_state(text) to sf_api, sf_worker, sf_system;

-- ===========================================================================
-- Grants (part 9, section 2)
-- ===========================================================================
grant usage on schema control, sync, data, events, obs, absurd to sf_api, sf_worker, sf_system;

grant select, insert, update, delete on all tables in schema control, sync, data, events, obs
  to sf_worker, sf_system;
grant usage, select on all sequences in schema control, sync, data, events, obs
  to sf_api, sf_worker, sf_system;

-- sf_api: everything except the wrapped private keys.
grant select, insert, update, delete on all tables in schema control, sync, data, events, obs to sf_api;
revoke all on control.environment from sf_api;
grant select (id, account_id, slug, name, is_production, settings, vault_public_key,
              vault_key_version, vault_previous_public_key, created_at, deleted_at),
      insert (id, account_id, slug, name, is_production, settings, vault_public_key,
              vault_private_key_wrapped, vault_key_version, created_at),
      update (name, settings, deleted_at, is_production)
  on control.environment to sf_api;
revoke all on control.platform_key from sf_api;
grant select (id, public_key, key_version) on control.platform_key to sf_api;

-- Audit is append-only for every application role.
revoke update, delete on obs.audit_event from sf_api, sf_worker, sf_system;

-- Absurd: the application roles spawn, claim and complete tasks.
grant select, insert, update, delete on all tables in schema absurd to sf_api, sf_worker, sf_system;
grant usage, select on all sequences in schema absurd to sf_api, sf_worker, sf_system;
grant create on schema absurd to sf_worker, sf_system;
alter default privileges in schema absurd
  grant select, insert, update, delete on tables to sf_api, sf_worker, sf_system;
alter default privileges for role sf_worker, sf_system in schema absurd
  grant select, insert, update, delete on tables to sf_api, sf_worker, sf_system;

-- Queues (part 1, section 5). Created here so their tables are owned by the
-- migrating role and covered by the default privileges above.
select absurd.create_queue('sync_interactive');
select absurd.create_queue('sync_bulk');
select absurd.create_queue('control');
select absurd.create_queue('delivery');
select absurd.create_queue('maintenance');
grant select, insert, update, delete on all tables in schema absurd to sf_api, sf_worker, sf_system;
