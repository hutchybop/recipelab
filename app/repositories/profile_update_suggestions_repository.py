from __future__ import annotations

from typing import Any, Mapping

from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database

from ..services.schema_utils import utc_now
from .common import to_object_id


class ProfileUpdateSuggestionsRepository:
    collection_name = "profile_update_suggestions"

    def __init__(self, db: Database):
        self.collection: Collection = db[self.collection_name]

    @classmethod
    def ensure_indexes(cls, db: Database) -> None:
        collection = db[cls.collection_name]
        collection.create_index(
            [("status", ASCENDING), ("created_at", DESCENDING)],
            name="profile_updates_status_created_at",
        )
        collection.create_index(
            [("action", ASCENDING), ("token", ASCENDING)],
            name="profile_updates_action_token",
        )

    def create(self, document: Mapping[str, Any]) -> dict[str, Any]:
        normalized = {
            "action": str(document.get("action", "")).strip(),
            "token": str(document.get("token", "")).strip().lower(),
            "support_count": int(document.get("support_count", 0)),
            "status": str(document.get("status", "pending")).strip() or "pending",
            "notes": str(document.get("notes", "")).strip(),
            "created_at": document.get("created_at") or utc_now(),
            "updated_at": utc_now(),
        }
        result = self.collection.insert_one(normalized)
        normalized["_id"] = result.inserted_id
        return normalized

    def get_by_id(self, suggestion_id: Any) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": to_object_id(suggestion_id)})

    def list_pending(self, *, limit: int = 100) -> list[dict[str, Any]]:
        cursor = (
            self.collection.find({"status": "pending"})
            .sort("created_at", DESCENDING)
            .limit(limit)
        )
        return list(cursor)

    def list_by_status(self, status: str, *, limit: int = 100) -> list[dict[str, Any]]:
        cursor = (
            self.collection.find({"status": status})
            .sort("updated_at", DESCENDING)
            .limit(limit)
        )
        return list(cursor)

    def update_status(self, suggestion_id: Any, status: str) -> bool:
        result = self.collection.update_one(
            {"_id": to_object_id(suggestion_id)},
            {"$set": {"status": status, "updated_at": utc_now()}},
        )
        return result.modified_count > 0

    def update_suggestion(
        self,
        suggestion_id: Any,
        *,
        action: str,
        token: str,
        status: str,
    ) -> bool:
        result = self.collection.update_one(
            {"_id": to_object_id(suggestion_id)},
            {
                "$set": {
                    "action": action,
                    "token": token,
                    "status": status,
                    "updated_at": utc_now(),
                }
            },
        )
        return result.modified_count > 0

    def delete_by_id(self, suggestion_id: Any) -> bool:
        result = self.collection.delete_many({"_id": to_object_id(suggestion_id)})
        return result.deleted_count > 0

    def reject_all_pending(self) -> int:
        result = self.collection.update_many(
            {"status": "pending"},
            {"$set": {"status": "rejected", "updated_at": utc_now()}},
        )
        return int(result.modified_count)
