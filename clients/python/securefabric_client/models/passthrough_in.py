from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.passthrough_in_query_type_0 import PassthroughInQueryType0


T = TypeVar("T", bound="PassthroughIn")


@_attrs_define
class PassthroughIn:
    """
    Attributes:
        path (str): Vendor API path; must match the connector's passthrough allowlist
        method (str | Unset):  Default: 'GET'.
        query (None | PassthroughInQueryType0 | Unset):
    """

    path: str
    method: str | Unset = "GET"
    query: None | PassthroughInQueryType0 | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.passthrough_in_query_type_0 import PassthroughInQueryType0  # noqa: PLC0415

        path = self.path

        method = self.method

        query: dict[str, Any] | None | Unset
        if isinstance(self.query, Unset):
            query = UNSET
        elif isinstance(self.query, PassthroughInQueryType0):
            query = self.query.to_dict()
        else:
            query = self.query

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "path": path,
            }
        )
        if method is not UNSET:
            field_dict["method"] = method
        if query is not UNSET:
            field_dict["query"] = query

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.passthrough_in_query_type_0 import PassthroughInQueryType0  # noqa: PLC0415

        d = dict(src_dict)
        path = d.pop("path")

        method = d.pop("method", UNSET)

        def _parse_query(data: object) -> None | PassthroughInQueryType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                query_type_0 = PassthroughInQueryType0.from_dict(data)

                return query_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | PassthroughInQueryType0 | Unset, data)

        query = _parse_query(d.pop("query", UNSET))

        passthrough_in = cls(
            path=path,
            method=method,
            query=query,
        )

        return passthrough_in
