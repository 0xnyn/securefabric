-- API call metering and cross-instance rate limits (API-07, usage).
--
-- Each API instance counts requests per environment in memory and flushes every
-- second. The API role (sf_api) has no direct rights on obs.api_rate_counter (an
-- internal table without RLS) or obs.usage_event (RLS, one tenant per transaction),
-- so the flush is this one SECURITY DEFINER function: add this instance's counts to
-- the shared window counters, record them as `api.calls` usage, and return the
-- window's totals across all instances.

create or replace function obs.flush_api_calls(
    p_window_start timestamptz,
    p_environment_ids uuid[],
    p_counts integer[]
)
returns table (environment_id uuid, calls integer)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
    if coalesce(array_length(p_environment_ids, 1), 0) <> coalesce(array_length(p_counts, 1), 0) then
        raise exception 'environment ids and counts differ in length';
    end if;
    if exists (select 1 from unnest(p_counts) as c(n) where n is null or n < 0) then
        raise exception 'counts must be non-negative';
    end if;

    insert into obs.api_rate_counter as c (environment_id, window_start, count)
    select e, p_window_start, n
      from unnest(p_environment_ids, p_counts) as t(e, n)
     where n > 0
    on conflict (environment_id, window_start) do update set count = c.count + excluded.count;

    insert into obs.usage_event (environment_id, kind, quantity)
    select e, 'api.calls', n
      from unnest(p_environment_ids, p_counts) as t(e, n)
     where n > 0;

    return query
        select r.environment_id, r.count
          from obs.api_rate_counter r
         where r.window_start = p_window_start;
end;
$$;

revoke all on function obs.flush_api_calls(timestamptz, uuid[], integer[]) from public;
grant execute on function obs.flush_api_calls(timestamptz, uuid[], integer[]) to sf_api;
