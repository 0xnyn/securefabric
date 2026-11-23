# securefabric-tasks

The contract layer between the API and the worker.
- `TaskSpec`: name, queue, retry defaults, and pydantic params and result models. `spawn()` validates and enqueues; `register()` attaches a typed handler.
- `contracts.py`: every task's models and spec.
- `Queue`: the queue names.
