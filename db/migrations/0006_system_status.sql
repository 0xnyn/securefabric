-- System status facts (GET /v1/status, `make status`, the dash's Status page).
--
-- The API runs as sf_api, which by design cannot read the migration ledger, the
-- Absurd queue tables or the worker heartbeat table. This one SECURITY DEFINER
-- function returns the operational facts those three surfaces show, and nothing
-- tenant-scoped: counts, versions and timings only. What each caller may see of it
-- (public summary, customer, operator) is decided in securefabric_domain.status.

create or replace function obs.system_status()
returns jsonb
language plpgsql
stable
security definer
set search_path = pg_catalog, public
as $$
declare
    q          record;
    counts     jsonb;
    v_queues   jsonb := '[]'::jsonb;
begin
    for q in select queue_name from absurd.queues order by queue_name loop
        execute format(
            $f$select jsonb_build_object(
                   'name', %L,
                   'pending',   count(*) filter (where state = 'pending'),
                   'running',   count(*) filter (where state = 'running'),
                   'sleeping',  count(*) filter (where state = 'sleeping'),
                   'completed', count(*) filter (where state = 'completed'),
                   'failed',    count(*) filter (where state = 'failed'),
                   'cancelled', count(*) filter (where state = 'cancelled'),
                   'oldest_pending_seconds',
                       extract(epoch from now() - min(enqueue_at) filter (where state = 'pending')))
                 from absurd.%I$f$,
            q.queue_name, 't_' || q.queue_name)
        into counts;
        v_queues := v_queues || counts;
    end loop;

    return jsonb_build_object(
        'database', jsonb_build_object(
            'server_version', current_setting('server_version'),
            'database', current_database(),
            'size_bytes', pg_database_size(current_database())),
        'migrations', coalesce(
            (select jsonb_agg(version order by version) from public.schema_migrations), '[]'::jsonb),
        'workers', coalesce((
            select jsonb_agg(jsonb_build_object(
                       'worker_id', worker_id, 'role', role, 'queues', queues,
                       'hostname', hostname, 'pid', pid, 'version', version,
                       'concurrency', concurrency, 'started_at', started_at,
                       'last_seen_at', last_seen_at,
                       'online', last_seen_at > now() - interval '20 seconds')
                   order by worker_id)
              from obs.worker_heartbeat), '[]'::jsonb),
        'queues', v_queues,
        'runs', coalesce((
            select jsonb_object_agg(state, n)
              from (select state, count(*) as n from sync.stream_run
                     where state in ('QUEUED', 'ADMITTED', 'RUNNING', 'PARKED', 'RETRY_WAIT')
                     group by state) s), '{}'::jsonb),
        'stuck_runs', (
            select count(*) from sync.stream_run
             where state = 'RUNNING' and started_at < now() - interval '15 minutes'),
        'failed_runs_last_day', (
            select count(*) from sync.stream_run
             where state = 'FAILED' and finished_at > now() - interval '1 day'),
        'alert_counts', coalesce((
            select jsonb_object_agg(severity, n)
              from (select severity, count(*) as n from obs.alert
                     where resolved_at is null group by severity) a), '{}'::jsonb),
        'alerts', coalesce((
            select jsonb_agg(jsonb_build_object(
                       'name', name, 'severity', severity, 'subject', subject,
                       'raised_at', raised_at, 'runbook', runbook)
                   order by raised_at desc)
              from (select * from obs.alert where resolved_at is null
                     order by raised_at desc limit 50) a), '[]'::jsonb)
    );
end;
$$;

revoke all on function obs.system_status() from public;
grant execute on function obs.system_status() to sf_api, sf_worker, sf_system;
