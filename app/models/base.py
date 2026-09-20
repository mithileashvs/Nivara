from datetime import datetime
from typing import Any

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field

from app.utils.time_utils import utcnow


class MongoModel(BaseModel):
    """Base for document shapes stored in MongoDB.

    Models are used to *build* documents with correct defaults before insertion;
    API input/output shapes live in ``app.schemas``.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, use_enum_values=True, populate_by_name=True)

    id: ObjectId = Field(default_factory=ObjectId, alias="_id")
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    def to_mongo(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)
