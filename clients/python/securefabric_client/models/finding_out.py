from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.finding_out_analytic_type_0 import FindingOutAnalyticType0
    from ..models.finding_out_enrichment_type_0 import FindingOutEnrichmentType0
    from ..models.finding_out_product_type_0 import FindingOutProductType0
    from ..models.finding_out_resource_related_item import FindingOutResourceRelatedItem
    from ..models.finding_out_resources_item import FindingOutResourcesItem
    from ..models.finding_out_ticket_type_0 import FindingOutTicketType0
    from ..models.finding_out_vulnerabilities_item import FindingOutVulnerabilitiesItem
    from ..models.meta import Meta
    from ..models.vendor_attributes import VendorAttributes


T = TypeVar("T", bound="FindingOut")


@_attrs_define
class FindingOut:
    """
    Attributes:
        id (str):
        title (None | str):
        description (None | str):
        severity (str):
        state (str):
        type_ (str):
        has_fix (bool | None):
        exploitable (bool | None):
        reachability (None | str):
        remediation (None | str):
        analytic (FindingOutAnalyticType0 | None):
        analytic_output (None | str):
        product (FindingOutProductType0 | None):
        ticket (FindingOutTicketType0 | None):
        resource_related (list[FindingOutResourceRelatedItem]):
        resources (list[FindingOutResourcesItem]):
        vulnerabilities (list[FindingOutVulnerabilitiesItem]):
        vendor_attributes (VendorAttributes):
        first_seen (None | str):
        last_seen (None | str):
        state_updated_at (None | str):
        connection_id (str):
        organization_id (str):
        cve_ids (list[str]):
        created_at (None | str):
        updated_at (None | str):
        deleted_at (None | str):
        enrichment (FindingOutEnrichmentType0 | None):
        field_meta (Meta):
    """

    id: str
    title: None | str
    description: None | str
    severity: str
    state: str
    type_: str
    has_fix: bool | None
    exploitable: bool | None
    reachability: None | str
    remediation: None | str
    analytic: FindingOutAnalyticType0 | None
    analytic_output: None | str
    product: FindingOutProductType0 | None
    ticket: FindingOutTicketType0 | None
    resource_related: list[FindingOutResourceRelatedItem]
    resources: list[FindingOutResourcesItem]
    vulnerabilities: list[FindingOutVulnerabilitiesItem]
    vendor_attributes: VendorAttributes
    first_seen: None | str
    last_seen: None | str
    state_updated_at: None | str
    connection_id: str
    organization_id: str
    cve_ids: list[str]
    created_at: None | str
    updated_at: None | str
    deleted_at: None | str
    enrichment: FindingOutEnrichmentType0 | None
    field_meta: Meta
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.finding_out_analytic_type_0 import FindingOutAnalyticType0  # noqa: PLC0415
        from ..models.finding_out_enrichment_type_0 import FindingOutEnrichmentType0  # noqa: PLC0415
        from ..models.finding_out_product_type_0 import FindingOutProductType0  # noqa: PLC0415
        from ..models.finding_out_ticket_type_0 import FindingOutTicketType0  # noqa: PLC0415

        id = self.id

        title: None | str
        title = self.title

        description: None | str
        description = self.description

        severity = self.severity

        state = self.state

        type_ = self.type_

        has_fix: bool | None
        has_fix = self.has_fix

        exploitable: bool | None
        exploitable = self.exploitable

        reachability: None | str
        reachability = self.reachability

        remediation: None | str
        remediation = self.remediation

        analytic: dict[str, Any] | None
        if isinstance(self.analytic, FindingOutAnalyticType0):
            analytic = self.analytic.to_dict()
        else:
            analytic = self.analytic

        analytic_output: None | str
        analytic_output = self.analytic_output

        product: dict[str, Any] | None
        if isinstance(self.product, FindingOutProductType0):
            product = self.product.to_dict()
        else:
            product = self.product

        ticket: dict[str, Any] | None
        if isinstance(self.ticket, FindingOutTicketType0):
            ticket = self.ticket.to_dict()
        else:
            ticket = self.ticket

        resource_related = []
        for resource_related_item_data in self.resource_related:
            resource_related_item = resource_related_item_data.to_dict()
            resource_related.append(resource_related_item)

        resources = []
        for resources_item_data in self.resources:
            resources_item = resources_item_data.to_dict()
            resources.append(resources_item)

        vulnerabilities = []
        for vulnerabilities_item_data in self.vulnerabilities:
            vulnerabilities_item = vulnerabilities_item_data.to_dict()
            vulnerabilities.append(vulnerabilities_item)

        vendor_attributes = self.vendor_attributes.to_dict()

        first_seen: None | str
        first_seen = self.first_seen

        last_seen: None | str
        last_seen = self.last_seen

        state_updated_at: None | str
        state_updated_at = self.state_updated_at

        connection_id = self.connection_id

        organization_id = self.organization_id

        cve_ids = self.cve_ids

        created_at: None | str
        created_at = self.created_at

        updated_at: None | str
        updated_at = self.updated_at

        deleted_at: None | str
        deleted_at = self.deleted_at

        enrichment: dict[str, Any] | None
        if isinstance(self.enrichment, FindingOutEnrichmentType0):
            enrichment = self.enrichment.to_dict()
        else:
            enrichment = self.enrichment

        field_meta = self.field_meta.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "title": title,
                "description": description,
                "severity": severity,
                "state": state,
                "type": type_,
                "has_fix": has_fix,
                "exploitable": exploitable,
                "reachability": reachability,
                "remediation": remediation,
                "analytic": analytic,
                "analytic_output": analytic_output,
                "product": product,
                "ticket": ticket,
                "resource_related": resource_related,
                "resources": resources,
                "vulnerabilities": vulnerabilities,
                "vendor_attributes": vendor_attributes,
                "first_seen": first_seen,
                "last_seen": last_seen,
                "state_updated_at": state_updated_at,
                "connection_id": connection_id,
                "organization_id": organization_id,
                "cve_ids": cve_ids,
                "created_at": created_at,
                "updated_at": updated_at,
                "deleted_at": deleted_at,
                "enrichment": enrichment,
                "_meta": field_meta,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.finding_out_analytic_type_0 import FindingOutAnalyticType0  # noqa: PLC0415
        from ..models.finding_out_enrichment_type_0 import FindingOutEnrichmentType0  # noqa: PLC0415
        from ..models.finding_out_product_type_0 import FindingOutProductType0  # noqa: PLC0415
        from ..models.finding_out_resource_related_item import FindingOutResourceRelatedItem  # noqa: PLC0415
        from ..models.finding_out_resources_item import FindingOutResourcesItem  # noqa: PLC0415
        from ..models.finding_out_ticket_type_0 import FindingOutTicketType0  # noqa: PLC0415
        from ..models.finding_out_vulnerabilities_item import FindingOutVulnerabilitiesItem  # noqa: PLC0415
        from ..models.meta import Meta  # noqa: PLC0415
        from ..models.vendor_attributes import VendorAttributes  # noqa: PLC0415

        d = dict(src_dict)
        id = d.pop("id")

        def _parse_title(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        title = _parse_title(d.pop("title"))

        def _parse_description(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        description = _parse_description(d.pop("description"))

        severity = d.pop("severity")

        state = d.pop("state")

        type_ = d.pop("type")

        def _parse_has_fix(data: object) -> bool | None:
            if data is None:
                return data
            return cast(bool | None, data)

        has_fix = _parse_has_fix(d.pop("has_fix"))

        def _parse_exploitable(data: object) -> bool | None:
            if data is None:
                return data
            return cast(bool | None, data)

        exploitable = _parse_exploitable(d.pop("exploitable"))

        def _parse_reachability(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        reachability = _parse_reachability(d.pop("reachability"))

        def _parse_remediation(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        remediation = _parse_remediation(d.pop("remediation"))

        def _parse_analytic(data: object) -> FindingOutAnalyticType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                analytic_type_0 = FindingOutAnalyticType0.from_dict(data)

                return analytic_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(FindingOutAnalyticType0 | None, data)

        analytic = _parse_analytic(d.pop("analytic"))

        def _parse_analytic_output(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        analytic_output = _parse_analytic_output(d.pop("analytic_output"))

        def _parse_product(data: object) -> FindingOutProductType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                product_type_0 = FindingOutProductType0.from_dict(data)

                return product_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(FindingOutProductType0 | None, data)

        product = _parse_product(d.pop("product"))

        def _parse_ticket(data: object) -> FindingOutTicketType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                ticket_type_0 = FindingOutTicketType0.from_dict(data)

                return ticket_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(FindingOutTicketType0 | None, data)

        ticket = _parse_ticket(d.pop("ticket"))

        resource_related = []
        _resource_related = d.pop("resource_related")
        for resource_related_item_data in _resource_related:
            resource_related_item = FindingOutResourceRelatedItem.from_dict(resource_related_item_data)

            resource_related.append(resource_related_item)

        resources = []
        _resources = d.pop("resources")
        for resources_item_data in _resources:
            resources_item = FindingOutResourcesItem.from_dict(resources_item_data)

            resources.append(resources_item)

        vulnerabilities = []
        _vulnerabilities = d.pop("vulnerabilities")
        for vulnerabilities_item_data in _vulnerabilities:
            vulnerabilities_item = FindingOutVulnerabilitiesItem.from_dict(vulnerabilities_item_data)

            vulnerabilities.append(vulnerabilities_item)

        vendor_attributes = VendorAttributes.from_dict(d.pop("vendor_attributes"))

        def _parse_first_seen(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        first_seen = _parse_first_seen(d.pop("first_seen"))

        def _parse_last_seen(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        last_seen = _parse_last_seen(d.pop("last_seen"))

        def _parse_state_updated_at(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        state_updated_at = _parse_state_updated_at(d.pop("state_updated_at"))

        connection_id = d.pop("connection_id")

        organization_id = d.pop("organization_id")

        cve_ids = cast(list[str], d.pop("cve_ids"))

        def _parse_created_at(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        created_at = _parse_created_at(d.pop("created_at"))

        def _parse_updated_at(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        updated_at = _parse_updated_at(d.pop("updated_at"))

        def _parse_deleted_at(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        deleted_at = _parse_deleted_at(d.pop("deleted_at"))

        def _parse_enrichment(data: object) -> FindingOutEnrichmentType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                enrichment_type_0 = FindingOutEnrichmentType0.from_dict(data)

                return enrichment_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(FindingOutEnrichmentType0 | None, data)

        enrichment = _parse_enrichment(d.pop("enrichment"))

        field_meta = Meta.from_dict(d.pop("_meta"))

        finding_out = cls(
            id=id,
            title=title,
            description=description,
            severity=severity,
            state=state,
            type_=type_,
            has_fix=has_fix,
            exploitable=exploitable,
            reachability=reachability,
            remediation=remediation,
            analytic=analytic,
            analytic_output=analytic_output,
            product=product,
            ticket=ticket,
            resource_related=resource_related,
            resources=resources,
            vulnerabilities=vulnerabilities,
            vendor_attributes=vendor_attributes,
            first_seen=first_seen,
            last_seen=last_seen,
            state_updated_at=state_updated_at,
            connection_id=connection_id,
            organization_id=organization_id,
            cve_ids=cve_ids,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=deleted_at,
            enrichment=enrichment,
            field_meta=field_meta,
        )

        finding_out.additional_properties = d
        return finding_out

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
