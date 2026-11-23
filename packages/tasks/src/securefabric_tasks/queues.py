"""Queue names. Each queue is served by its own worker process(es)."""

from enum import StrEnum


class Queue(StrEnum):
    DEFAULT = "default"
