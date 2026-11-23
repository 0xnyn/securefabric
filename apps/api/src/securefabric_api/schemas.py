"""Base classes for API schemas."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer, WithJsonSchema

from securefabric_core.canonical import format_datetime

# A response timestamp: ISO 8601 UTC with milliseconds (NORM-13), typed as a date-time
# string in the OpenAPI document. (A catch-all serializer would erase every field's type.)
Timestamp = Annotated[
    datetime,
    PlainSerializer(format_datetime, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "format": "date-time"}, mode="serialization"),
]


class ResponseModel(BaseModel):
    """Base for every response body.

    A field with a default is still always *sent*, so its serialization schema marks
    it required; the generated TypeScript client then types it as present. Timestamp
    fields use ``Timestamp`` (ISO 8601 UTC with milliseconds, NORM-13).
    """

    model_config = ConfigDict(
        json_schema_serialization_defaults_required=True, from_attributes=True
    )


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
