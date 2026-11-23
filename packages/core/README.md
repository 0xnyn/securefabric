# securefabric-core

Shared building blocks with no infrastructure dependencies:
- `BaseServiceSettings`: environment, debug and logging settings that every service extends.
- `configure_logging` / `get_logger`: structlog routed through the stdlib, as console or JSON output. Uvicorn logs use the same format.
- `AppError` and subclasses: transport-agnostic domain errors. Each app maps them to its own transport.
