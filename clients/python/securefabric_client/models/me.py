from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.account_out import AccountOut
    from ..models.environment_out import EnvironmentOut


T = TypeVar("T", bound="Me")


@_attrs_define
class Me:
    """
    Attributes:
        kind (str):
        actor_id (str):
        email (None | str):
        name (None | str):
        role (None | str):
        is_operator (bool):  Default: False.
        scopes (list[str]):
        account (AccountOut | None):
        environment_id (None | UUID):
        environments (list[EnvironmentOut]):
        needs_onboarding (bool):  Default: False.
    """

    kind: str
    actor_id: str
    email: None | str
    name: None | str
    role: None | str
    scopes: list[str]
    account: AccountOut | None
    environment_id: None | UUID
    environments: list[EnvironmentOut]
    is_operator: bool = False
    needs_onboarding: bool = False
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.account_out import AccountOut  # noqa: PLC0415

        kind = self.kind

        actor_id = self.actor_id

        email: None | str
        email = self.email

        name: None | str
        name = self.name

        role: None | str
        role = self.role

        is_operator = self.is_operator

        scopes = self.scopes

        account: dict[str, Any] | None
        if isinstance(self.account, AccountOut):
            account = self.account.to_dict()
        else:
            account = self.account

        environment_id: None | str
        if isinstance(self.environment_id, UUID):
            environment_id = str(self.environment_id)
        else:
            environment_id = self.environment_id

        environments = []
        for environments_item_data in self.environments:
            environments_item = environments_item_data.to_dict()
            environments.append(environments_item)

        needs_onboarding = self.needs_onboarding

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "kind": kind,
                "actor_id": actor_id,
                "email": email,
                "name": name,
                "role": role,
                "is_operator": is_operator,
                "scopes": scopes,
                "account": account,
                "environment_id": environment_id,
                "environments": environments,
                "needs_onboarding": needs_onboarding,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.account_out import AccountOut  # noqa: PLC0415
        from ..models.environment_out import EnvironmentOut  # noqa: PLC0415

        d = dict(src_dict)
        kind = d.pop("kind")

        actor_id = d.pop("actor_id")

        def _parse_email(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        email = _parse_email(d.pop("email"))

        def _parse_name(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        name = _parse_name(d.pop("name"))

        def _parse_role(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        role = _parse_role(d.pop("role"))

        is_operator = d.pop("is_operator")

        scopes = cast(list[str], d.pop("scopes"))

        def _parse_account(data: object) -> AccountOut | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                account_type_0 = AccountOut.from_dict(data)

                return account_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(AccountOut | None, data)

        account = _parse_account(d.pop("account"))

        def _parse_environment_id(data: object) -> None | UUID:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                environment_id_type_0 = UUID(data)

                return environment_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        environment_id = _parse_environment_id(d.pop("environment_id"))

        environments = []
        _environments = d.pop("environments")
        for environments_item_data in _environments:
            environments_item = EnvironmentOut.from_dict(environments_item_data)

            environments.append(environments_item)

        needs_onboarding = d.pop("needs_onboarding")

        me = cls(
            kind=kind,
            actor_id=actor_id,
            email=email,
            name=name,
            role=role,
            is_operator=is_operator,
            scopes=scopes,
            account=account,
            environment_id=environment_id,
            environments=environments,
            needs_onboarding=needs_onboarding,
        )

        me.additional_properties = d
        return me

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
