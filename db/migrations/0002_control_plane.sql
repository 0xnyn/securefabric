-- 0002_control_plane
-- The control plane behind the dash: one workspace (team), its members, and
-- environments holding API keys, webhooks, variables, integrations,
-- connections, sync jobs and operations (logs).
-- Forward-only. Never edit after it has been applied anywhere.

create schema if not exists fabric;

-- One row: the team this deployment serves.
create table fabric.workspace (
    id          smallint primary key default 1 check (id = 1),
    team_name   text not null,
    team_plan   text not null,
    team_slug   text not null,
    user_name   text not null,
    user_email  text not null,
    seeded_at   timestamptz not null default now()
);

create table fabric.members (
    id          text primary key,
    email       text not null unique,
    name        text not null,
    role        text not null check (role in ('Full access', 'Contributor', 'Support')),
    joined_at   timestamptz,
    created_at  timestamptz not null default now()
);

create table fabric.environments (
    id                   text primary key,
    slug                 text not null unique check (slug ~ '^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$'),
    name                 text not null,
    is_production        boolean not null default false,
    callback_url         text not null,
    connect              jsonb not null,
    default_key_secret   text not null,
    keys_rotated_at      timestamptz not null default now(),
    webhook_secret       text not null,
    created_at           timestamptz not null default now()
);

create table fabric.api_keys (
    id              text primary key,
    environment_id  text not null references fabric.environments (id) on delete cascade,
    name            text not null,
    preview         text not null,
    secret_sha256   text not null,
    scopes          text[] not null,
    is_default      boolean not null default false,
    created_by      text not null,
    created_at      timestamptz not null default now(),
    last_used_at    timestamptz
);
create index api_keys_environment_idx on fabric.api_keys (environment_id, created_at);

create table fabric.integrations (
    environment_id  text not null references fabric.environments (id) on delete cascade,
    id              text not null,
    provider        text not null,
    display_name    text not null,
    models          text[] not null,
    sync_frequency  text not null check (sync_frequency in ('15m', '1h', '4h', '12h', '24h')),
    write_scopes    text[] not null default '{}',
    allow_sandbox   boolean not null default true,
    created_at      timestamptz not null default now(),
    primary key (environment_id, id)
);

create table fabric.connections (
    id                  text primary key,
    environment_id      text not null,
    integration_id      text not null,
    provider            text not null,
    customer            jsonb not null,
    domain              text not null,
    sandbox             boolean not null default false,
    paused              boolean not null default false,
    health              text not null,
    credentials         jsonb not null default '{}',
    counts              jsonb not null default '{}',
    tags                jsonb not null default '{}',
    metadata            jsonb not null default '{}',
    frequency_override  text,
    webhook_override    text,
    created_at          timestamptz not null default now(),
    last_sync_at        timestamptz,
    -- Renaming an integration's key carries its connections along.
    foreign key (environment_id, integration_id)
        references fabric.integrations (environment_id, id)
        on update cascade on delete cascade
);
create index connections_environment_idx on fabric.connections (environment_id, created_at desc);

create table fabric.sync_jobs (
    id              text primary key,
    connection_id   text not null references fabric.connections (id) on delete cascade,
    type            text not null check (type in ('INITIAL', 'SCHEDULED', 'ON_DEMAND')),
    status          text not null check (status in ('QUEUED', 'RUNNING', 'SUCCESS', 'FAILED')),
    started_at      timestamptz not null default now(),
    duration_ms     integer,
    added           integer not null default 0,
    updated         integer not null default 0,
    deleted         integer not null default 0,
    failure_reason  text,
    task_id         text
);
create index sync_jobs_connection_idx on fabric.sync_jobs (connection_id, started_at desc);
create index sync_jobs_running_idx on fabric.sync_jobs (status) where status in ('QUEUED', 'RUNNING');

-- Logs. Deliberately no FK to connections: history outlives a deleted connection.
create table fabric.operations (
    id              text primary key,
    environment_id  text not null references fabric.environments (id) on delete cascade,
    connection_id   text,
    integration_id  text,
    provider        text,
    customer        text,
    type            text not null check (type in ('auth', 'sync', 'api', 'action', 'proxy', 'webhook')),
    action          text not null,
    status          text not null check (status in ('success', 'failed', 'running', 'warning')),
    status_code     integer,
    method          text,
    path            text,
    records         integer,
    duration_ms     integer not null default 0,
    started_at      timestamptz not null default now()
);
create index operations_environment_idx on fabric.operations (environment_id, started_at desc);

create table fabric.webhooks (
    id              text primary key,
    environment_id  text not null references fabric.environments (id) on delete cascade,
    url             text not null,
    description     text not null default '',
    disabled        boolean not null default false,
    events          text[] not null,
    created_at      timestamptz not null default now()
);

create table fabric.variables (
    environment_id  text not null references fabric.environments (id) on delete cascade,
    key             text not null,
    value           text not null,
    secret          boolean not null default false,
    created_at      timestamptz not null default now(),
    primary key (environment_id, key)
);

-- Liveness for `make status` and GET /api/v1/status: each worker process
-- upserts its row every few seconds; stale rows mean the worker is gone.
create table fabric.worker_heartbeats (
    worker_id     text primary key,
    queue         text not null,
    hostname      text not null,
    pid           integer not null,
    version       text not null,
    concurrency   integer not null,
    started_at    timestamptz not null,
    last_seen_at  timestamptz not null default now()
);
