-- 0003_actions
-- The action plane (docs/plan/07-public-api-and-events.md, section 7; ACT-02, ACT-03).
-- One row per write-back request; the control worker performs it against the vendor.

create table control.action (
    id               uuid primary key default absurd.portable_uuidv7(),
    environment_id   uuid not null references control.environment (id) on delete cascade,
    connection_id    uuid not null,
    finding_id       uuid not null,
    name             text not null,
    params           jsonb not null,
    status           text not null default 'PENDING' check (status in ('PENDING', 'SUCCEEDED', 'FAILED')),
    vendor_response  jsonb,
    message          text,
    requested_by     text,
    request_id       text,
    created_at       timestamptz not null default now(),
    finished_at      timestamptz
);
create index action_finding on control.action (finding_id, created_at desc);

alter table control.action enable row level security;
create policy tenant_isolation on control.action
  using (environment_id = control.current_environment_id())
  with check (environment_id = control.current_environment_id());

grant select, insert, update, delete on control.action to sf_api, sf_worker, sf_system;
