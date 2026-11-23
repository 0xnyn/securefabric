"""``securefabric-worker [--role scheduler|sync|control|delivery|maintenance|all]``."""

import asyncio

from securefabric_worker.config import WorkerSettings
from securefabric_worker.main import parse_args, run


def main() -> None:
    args = parse_args()
    settings = WorkerSettings(role=args.role) if args.role else WorkerSettings()
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
