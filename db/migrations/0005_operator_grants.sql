-- 0005_operator_grants
-- Workers also run operator repairs (re-normalisation, purge, raw page reads).
grant execute on function control.operator_search(text) to sf_worker;
grant execute on function control.operator_scheduler() to sf_worker;
grant execute on function control.operator_environment(uuid) to sf_worker;
