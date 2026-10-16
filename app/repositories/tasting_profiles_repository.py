from __future__ import annotations

from typing import Any, Mapping

from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database

from ..services.schema_utils import (
    normalize_tasting_profile_document,
    normalize_tasting_profile_status,
    utc_now,
)
from .common import to_object_id


class TastingProfilesRepository:
    collection_name = "tasting_profiles"

    def __init__(self, db: Database):
        self.collection: Collection = db[self.collection_name]

    @classmethod
    def ensure_indexes(cls, db: Database) -> None:
        collection = db[cls.collection_name]
        collection.create_index(
            [("status", ASCENDING), ("created_at", DESCENDING)],
            name="tasting_profiles_status_created_at",
        )
        collection.create_index(
            [("is_active", ASCENDING)],
            unique=True,
            partialFilterExpression={"is_active": True},
            name="tasting_profiles_is_active_unique",
        )
        collection.create_index(
            [("generation_run_id", ASCENDING)],
            name="tasting_profiles_generation_run_id",
        )

    def create_candidate(self, document: Mapping[str, Any]) -> dict[str, Any]:
        normalized = normalize_tasting_profile_document(
            {
                **dict(document),
                "status": "candidate_pending",
                "is_active": False,
                "review": {
                    "decision": "pending",
                    "decision_note": str(
                        (document.get("review") or {}).get("decision_note", "")
                    ).strip(),
                    "decided_at": None,
                },
            }
        )
        result = self.collection.insert_one(normalized)
        normalized["_id"] = result.inserted_id
        return normalized

    def get_by_id(self, profile_id: Any) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": to_object_id(profile_id)})

    def get_active_profile(self) -> dict[str, Any] | None:
        return self.collection.find_one({"is_active": True, "status": "accepted"})

    def get_latest_candidate(self) -> dict[str, Any] | None:
        records = list(
            self.collection.find({"status": "candidate_pending"})
            .sort("created_at", DESCENDING)
            .limit(1)
        )
        return records[0] if records else None

    def list_by_status(self, status: str, *, limit: int = 100) -> list[dict[str, Any]]:
        normalized_status = normalize_tasting_profile_status(status)
        cursor = (
            self.collection.find({"status": normalized_status})
            .sort("created_at", DESCENDING)
            .limit(limit)
        )
        return list(cursor)

    def accept_candidate(self, profile_id: Any, *, decision_note: str = "") -> bool:
        now = utc_now()
        candidate = self.collection.find_one(
            {
                "_id": to_object_id(profile_id),
                "status": "candidate_pending",
            }
        )
        if not candidate:
            return False

        self.collection.update_many(
            {"is_active": True, "status": "accepted"},
            {
                "$set": {
                    "status": "superseded",
                    "is_active": False,
                    "superseded_at": now,
                    "updated_at": now,
                }
            },
        )

        result = self.collection.update_one(
            {"_id": candidate["_id"], "status": "candidate_pending"},
            {
                "$set": {
                    "status": "accepted",
                    "is_active": True,
                    "accepted_at": now,
                    "updated_at": now,
                    "review": {
                        "decision": "accepted",
                        "decision_note": str(decision_note).strip(),
                        "decided_at": now,
                    },
                }
            },
        )
        return result.modified_count > 0

    def reject_candidate(self, profile_id: Any, *, decision_note: str = "") -> bool:
        now = utc_now()
        result = self.collection.update_one(
            {
                "_id": to_object_id(profile_id),
                "status": "candidate_pending",
            },
            {
                "$set": {
                    "status": "rejected",
                    "is_active": False,
                    "rejected_at": now,
                    "updated_at": now,
                    "review": {
                        "decision": "rejected",
                        "decision_note": str(decision_note).strip(),
                        "decided_at": now,
                    },
                }
            },
        )
        return result.modified_count > 0
