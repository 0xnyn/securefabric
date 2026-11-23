-- Fix obs.flush_api_calls (0007): the RETURNS TABLE column `environment_id` shadowed
-- the table column in ON CONFLICT ("column reference is ambiguous"). Name the
-- conflict target by constraint and qualify every column. Same signature, so the
-- grants from 0007 carry over.

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
    select t.e, p_window_start, t.n
      from unnest(p_environment_ids, p_counts) as t(e, n)
     where t.n > 0
    on conflict on constraint api_rate_counter_pkey
    do update set count = c.count + excluded.count;

    insert into obs.usage_event (environment_id, kind, quantity)
    select t.e, 'api.calls', t.n
      from unnest(p_environment_ids, p_counts) as t(e, n)
     where t.n > 0;

    return query
        select r.environment_id, r.count
          from obs.api_rate_counter r
         where r.window_start = p_window_start;
end;
$$;
