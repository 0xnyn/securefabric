# securefabric-api

FastAPI service. Entry point: `securefabric-api` (or `uvicorn --factory securefabric_api.main:create_app`).

- `main.py`: app factory. The lifespan opens and closes the psycopg pool; also wires middleware and error handlers.
- `dependencies.py`: `get_absurd` gives each request an `AsyncAbsurd` bound to a pooled connection.
- `api/health.py`: `/health/live` and `/health/ready` (readiness checks the DB).
- `api/v1/tenants.py`: `POST /api/v1/tenants` spawns `provision-tenant` (respects the `Idempotency-Key` header).
- `api/v1/tasks.py`: `GET /api/v1/tasks/{id}` returns status and result; `POST /api/v1/tasks/{id}/cancel` cancels.

Errors always use the envelope `{"error": {"code", "message", "details?"}}`. Each request gets an `X-Request-ID`, which is also bound into every log line.
