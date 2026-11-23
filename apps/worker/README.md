# securefabric-worker

Absurd worker. Entry point: `securefabric-worker`.

On startup it registers every handler in `handlers/`. It also creates its queue, with a retention policy, unless `WORKER_AUTO_CREATE_QUEUE=false`. Then it claims tasks with `WORKER_CONCURRENCY` concurrent slots. On SIGINT or SIGTERM it stops claiming new work and lets in-flight tasks finish.

Each worker process serves one queue (`WORKER_QUEUE`). To scale, run more processes: `make scale-worker n=4`.
