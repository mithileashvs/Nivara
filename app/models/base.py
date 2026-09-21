from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.utils.time_utils import utcnow


class EntityModel(BaseModel):
    """Base for entity data models.

    Models build record dicts with correct defaults before database insertion.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, use_enum_values=True, populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        d = self.model_dump(by_alias=True)
        if "_id" in d:
            d["id"] = str(d["_id"])
        return d

    def to_mongo(self) -> dict[str, Any]:
        return self.to_dict()


# Alias for backward compatibility during migration
MongoModel = EntityModel
