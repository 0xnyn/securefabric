"""Base classes for API schemas."""

from pydantic import BaseModel, ConfigDict


class ResponseModel(BaseModel):
    """Base for every response body.

    A field with a default is still always *sent*, so its serialization schema marks
    it required. The generated TypeScript client then types ``status: "ok"`` rather
    than ``status?: "ok"``, while request models keep defaulted fields optional.
    """

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
