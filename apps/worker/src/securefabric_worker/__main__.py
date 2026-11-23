"""``python -m securefabric_worker`` / ``securefabric-worker`` entrypoint."""

import asyncio

from securefabric_worker.main import run


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
