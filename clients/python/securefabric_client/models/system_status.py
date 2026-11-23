from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.system_status_alert_counts import SystemStatusAlertCounts
    from ..models.system_status_alerts_item import SystemStatusAlertsItem
    from ..models.system_status_database import SystemStatusDatabase
    from ..models.system_status_migrations import SystemStatusMigrations
    from ..models.system_status_queues_item import SystemStatusQueuesItem
    from ..models.system_status_runs import SystemStatusRuns
    from ..models.system_status_workers_item import SystemStatusWorkersItem


T = TypeVar("T", bound="SystemStatus")


@_attrs_define
class SystemStatus:
    """
    Attributes:
        status (str):
        problems (list[str]):
        version (str):
        uptime_seconds (float | None):
        database (SystemStatusDatabase):
        migrations (SystemStatusMigrations):
        workers (list[SystemStatusWorkersItem]):
        queues (list[SystemStatusQueuesItem]):
        runs (SystemStatusRuns):
        stuck_runs (int):
        failed_runs_last_day (int):
        alert_counts (SystemStatusAlertCounts):
        alerts (list[SystemStatusAlertsItem]):
        checked_at (datetime.datetime):
    """

    status: str
    problems: list[str]
    version: str
    uptime_seconds: float | None
    database: SystemStatusDatabase
    migrations: SystemStatusMigrations
    workers: list[SystemStatusWorkersItem]
    queues: list[SystemStatusQueuesItem]
    runs: SystemStatusRuns
    stuck_runs: int
    failed_runs_last_day: int
    alert_counts: SystemStatusAlertCounts
    alerts: list[SystemStatusAlertsItem]
    checked_at: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        status = self.status

        problems = self.problems

        version = self.version

        uptime_seconds: float | None
        uptime_seconds = self.uptime_seconds

        database = self.database.to_dict()

        migrations = self.migrations.to_dict()

        workers = []
        for workers_item_data in self.workers:
            workers_item = workers_item_data.to_dict()
            workers.append(workers_item)

        queues = []
        for queues_item_data in self.queues:
            queues_item = queues_item_data.to_dict()
            queues.append(queues_item)

        runs = self.runs.to_dict()

        stuck_runs = self.stuck_runs

        failed_runs_last_day = self.failed_runs_last_day

        alert_counts = self.alert_counts.to_dict()

        alerts = []
        for alerts_item_data in self.alerts:
            alerts_item = alerts_item_data.to_dict()
            alerts.append(alerts_item)

        checked_at = self.checked_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "status": status,
                "problems": problems,
                "version": version,
                "uptime_seconds": uptime_seconds,
                "database": database,
                "migrations": migrations,
                "workers": workers,
                "queues": queues,
                "runs": runs,
                "stuck_runs": stuck_runs,
                "failed_runs_last_day": failed_runs_last_day,
                "alert_counts": alert_counts,
                "alerts": alerts,
                "checked_at": checked_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.system_status_alert_counts import SystemStatusAlertCounts  # noqa: PLC0415
        from ..models.system_status_alerts_item import SystemStatusAlertsItem  # noqa: PLC0415
        from ..models.system_status_database import SystemStatusDatabase  # noqa: PLC0415
        from ..models.system_status_migrations import SystemStatusMigrations  # noqa: PLC0415
        from ..models.system_status_queues_item import SystemStatusQueuesItem  # noqa: PLC0415
        from ..models.system_status_runs import SystemStatusRuns  # noqa: PLC0415
        from ..models.system_status_workers_item import SystemStatusWorkersItem  # noqa: PLC0415

        d = dict(src_dict)
        status = d.pop("status")

        problems = cast(list[str], d.pop("problems"))

        version = d.pop("version")

        def _parse_uptime_seconds(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        uptime_seconds = _parse_uptime_seconds(d.pop("uptime_seconds"))

        database = SystemStatusDatabase.from_dict(d.pop("database"))

        migrations = SystemStatusMigrations.from_dict(d.pop("migrations"))

        workers = []
        _workers = d.pop("workers")
        for workers_item_data in _workers:
            workers_item = SystemStatusWorkersItem.from_dict(workers_item_data)

            workers.append(workers_item)

        queues = []
        _queues = d.pop("queues")
        for queues_item_data in _queues:
            queues_item = SystemStatusQueuesItem.from_dict(queues_item_data)

            queues.append(queues_item)

        runs = SystemStatusRuns.from_dict(d.pop("runs"))

        stuck_runs = d.pop("stuck_runs")

        failed_runs_last_day = d.pop("failed_runs_last_day")

        alert_counts = SystemStatusAlertCounts.from_dict(d.pop("alert_counts"))

        alerts = []
        _alerts = d.pop("alerts")
        for alerts_item_data in _alerts:
            alerts_item = SystemStatusAlertsItem.from_dict(alerts_item_data)

            alerts.append(alerts_item)

        checked_at = datetime.datetime.fromisoformat(d.pop("checked_at"))

        system_status = cls(
            status=status,
            problems=problems,
            version=version,
            uptime_seconds=uptime_seconds,
            database=database,
            migrations=migrations,
            workers=workers,
            queues=queues,
            runs=runs,
            stuck_runs=stuck_runs,
            failed_runs_last_day=failed_runs_last_day,
            alert_counts=alert_counts,
            alerts=alerts,
            checked_at=checked_at,
        )

        system_status.additional_properties = d
        return system_status

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
