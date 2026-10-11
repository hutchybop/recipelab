from __future__ import annotations

import re
from collections import Counter
from typing import Any

from pymongo.database import Database

from ..repositories import (
    FeedbackEventsRepository,
    PreferencesRepository,
    ProfileUpdateSuggestionsRepository,
    RecipesRepository,
    SuggestionsRepository,
)

_TOKEN_PATTERN = re.compile(r"[a-z]+")
_INGREDIENT_MODIFIERS = {
    "about",
    "boneless",
    "chopped",
    "cored",
    "crushed",
    "diced",
    "divided",
    "drained",
    "finely",
    "fresh",
    "halved",
    "large",
    "medium",
    "minced",
    "optional",
    "peeled",
    "quartered",
    "rinsed",
    "roughly",
    "small",
    "seeded",
    "skinless",
    "sliced",
    "thin",
    "thick",
    "thickly",
    "thinly",
    "trimmed",
    "toasted",
    "warmed",
    "grated",
    "shredded",
    "melted",
    "softened",
    "cooked",
    "uncooked",
    "removed",
    "discarded",
    "reserved",
    "taste",
    "minutes",
    "minute",
    "tablespoon",
    "tablespoons",
    "teaspoon",
    "teaspoons",
    "cups",
    "cup",
    "clove",
    "cloves",
    "piece",
    "pieces",
    "pinch",
    "of",
    "and",
    "as",
    "needed",
    "for",
    "serving",
    "garnish",
}
_NON_SPECIFIC_PHRASES = {
    "black",
    "brown",
    "dark",
    "green",
    "light",
    "orange",
    "purple",
    "red",
    "white",
    "yellow",
    "thin",
    "thick",
}


def generate_profile_update_suggestions(
    db: Database, *, min_support: int = 2, limit: int = 300
) -> dict[str, Any]:
    feedback_repo = FeedbackEventsRepository(db)
    preferences_repo = PreferencesRepository(db)
    profile_updates_repo = ProfileUpdateSuggestionsRepository(db)
    recipes_repo = RecipesRepository(db)
    suggestions_repo = SuggestionsRepository(db)

    active_profile = preferences_repo.get_active_profile() or {
        "profile_name": "default",
        "active": True,
        "hard_avoids": [],
        "likes": [],
        "dislikes": [],
        "notes": "",
        "weights": {},
    }

    liked_counts: Counter[str] = Counter()
    disliked_counts: Counter[str] = Counter()

    events = feedback_repo.list_recent(limit=limit)
    latest_reactions_by_target: list[dict[str, Any]] = []
    seen_targets: set[tuple[str, str]] = set()
    for event in events:
        signal = str(event.get("signal", "")).strip()
        if signal not in {"liked", "disliked"}:
            continue

        target_type = str(event.get("target_type", "")).strip()
        target_id = str(event.get("target_id", "")).strip()
        if not target_type or not target_id:
            continue

        key = (target_type, target_id)
        if key in seen_targets:
            continue
        seen_targets.add(key)
        latest_reactions_by_target.append(event)

    for event in latest_reactions_by_target:
        signal = event.get("signal")
        target_recipe = _resolve_target_recipe(
            event=event,
            recipes_repo=recipes_repo,
            suggestions_repo=suggestions_repo,
        )
        if not target_recipe:
            continue

        tokens = _extract_tokens(target_recipe)
        if signal == "liked":
            liked_counts.update(tokens)
        else:
            disliked_counts.update(tokens)

    likes = {_normalize_phrase(item) for item in active_profile.get("likes", [])}
    dislikes = {_normalize_phrase(item) for item in active_profile.get("dislikes", [])}
    hard_avoids = {
        _normalize_phrase(item) for item in active_profile.get("hard_avoids", [])
    }
    suppressed_suggestions = set()
    for status in ("rejected", "reverted"):
        suppressed_suggestions.update(
            (
                item.get("action"),
                _normalize_phrase(item.get("token", "")),
            )
            for item in profile_updates_repo.list_by_status(status, limit=1000)
        )

    candidates: dict[tuple[str, str], int] = {}
    for token, count in liked_counts.items():
        if count < min_support:
            continue
        if token in likes or token in dislikes or token in hard_avoids:
            continue
        key = ("add_like", token)
        if key not in suppressed_suggestions:
            candidates[key] = count

    for token, count in disliked_counts.items():
        if count < min_support:
            continue
        if token in dislikes or token in likes or token in hard_avoids:
            continue
        key = ("add_dislike", token)
        if key not in suppressed_suggestions:
            candidates[key] = count

    existing_pending = set()
    for item in profile_updates_repo.list_pending(limit=500):
        key = (item.get("action"), _normalize_phrase(item.get("token", "")))
        if key in candidates:
            existing_pending.add(key)
        else:
            # A refresh replaces stale proposals, including one-word candidates
            # created by the previous ingredient tokenizer.
            profile_updates_repo.update_status(item.get("_id"), "rejected")

    created = 0
    for (action, token), count in candidates.items():
        key = (action, token)
        if key in existing_pending:
            continue
        profile_updates_repo.create(
            {
                "action": action,
                "token": token,
                "support_count": count,
                "status": "pending",
                "notes": f"Observed in {count} {action.removeprefix('add_')} feedback events.",
            }
        )
        existing_pending.add(key)
        created += 1

    return {
        "created": created,
        "pending_total": len(profile_updates_repo.list_pending(limit=500)),
    }


def apply_profile_update_suggestion(
    db: Database, suggestion_id: str
) -> tuple[bool, str]:
    profile_updates_repo = ProfileUpdateSuggestionsRepository(db)
    preferences_repo = PreferencesRepository(db)

    suggestion = profile_updates_repo.get_by_id(suggestion_id)
    if not suggestion:
        return False, "Suggestion not found"
    if suggestion.get("status") != "pending":
        return False, "Suggestion is not pending"

    profile = preferences_repo.get_active_profile() or {
        "profile_name": "default",
        "active": True,
        "hard_avoids": [],
        "likes": [],
        "dislikes": [],
        "notes": "",
        "weights": {},
    }
    token = _normalize_phrase(suggestion.get("token", ""))
    action = suggestion.get("action")
    hard_avoids = {_normalize_phrase(item) for item in profile.get("hard_avoids", [])}
    if action not in {"add_like", "add_dislike"} or not token:
        return False, "No applicable change"
    if token in hard_avoids:
        return False, "A hard avoid cannot also be a profile like or dislike"

    _add_preference(profile, action, token)

    preferences_repo.upsert_profile(
        {
            "profile_name": profile.get("profile_name", "default"),
            "active": True,
            "hard_avoids": profile.get("hard_avoids", []),
            "likes": profile.get("likes", []),
            "dislikes": profile.get("dislikes", []),
            "notes": profile.get("notes", ""),
            "weights": profile.get("weights", {}),
        }
    )
    profile_updates_repo.update_status(suggestion_id, "applied")
    return True, "Profile updated"


def reject_profile_update_suggestion(db: Database, suggestion_id: str) -> bool:
    repository = ProfileUpdateSuggestionsRepository(db)
    suggestion = repository.get_by_id(suggestion_id)
    if not suggestion or suggestion.get("status") != "pending":
        return False
    return repository.update_status(suggestion_id, "rejected")


def edit_profile_update_suggestion(
    db: Database, suggestion_id: str, *, action: str, token: str
) -> tuple[bool, str]:
    repository = ProfileUpdateSuggestionsRepository(db)
    suggestion = repository.get_by_id(suggestion_id)
    if not suggestion:
        return False, "Suggestion not found"

    action = str(action).strip()
    token = _normalize_phrase(token)
    if action not in {"add_like", "add_dislike"} or not token:
        return False, "Enter a preference and choose like or dislike"

    status = str(suggestion.get("status", ""))
    old_action = suggestion.get("action")
    old_token = _normalize_phrase(suggestion.get("token", ""))
    if status == "applied":
        preferences_repo = PreferencesRepository(db)
        profile = _get_active_profile(preferences_repo)
        hard_avoids = {
            _normalize_phrase(item) for item in profile.get("hard_avoids", [])
        }
        if token in hard_avoids:
            return False, "A hard avoid cannot also be a profile like or dislike"
        _remove_preference(profile, old_action, old_token)
        _add_preference(profile, action, token)
        preferences_repo.upsert_profile(profile)
    elif status not in {"pending", "rejected", "reverted"}:
        return False, "Suggestion cannot be edited in its current state"

    updated = repository.update_suggestion(
        suggestion_id, action=action, token=token, status=status
    )
    if not updated:
        return False, "Suggestion was not changed"
    return True, "Suggestion updated"


def undo_profile_update_suggestion(
    db: Database, suggestion_id: str
) -> tuple[bool, str]:
    repository = ProfileUpdateSuggestionsRepository(db)
    suggestion = repository.get_by_id(suggestion_id)
    if not suggestion:
        return False, "Suggestion not found"
    if suggestion.get("status") != "applied":
        return False, "Only applied suggestions can be undone"

    preferences_repo = PreferencesRepository(db)
    profile = _get_active_profile(preferences_repo)
    _remove_preference(
        profile,
        suggestion.get("action"),
        _normalize_phrase(suggestion.get("token", "")),
    )
    preferences_repo.upsert_profile(profile)
    repository.update_status(suggestion_id, "reverted")
    return True, "Suggestion undone and removed from the active profile"


def reopen_profile_update_suggestion(db: Database, suggestion_id: str) -> bool:
    repository = ProfileUpdateSuggestionsRepository(db)
    suggestion = repository.get_by_id(suggestion_id)
    if not suggestion or suggestion.get("status") not in {"rejected", "reverted"}:
        return False
    return repository.update_status(suggestion_id, "pending")


def delete_profile_update_suggestion(
    db: Database, suggestion_id: str
) -> tuple[bool, str]:
    repository = ProfileUpdateSuggestionsRepository(db)
    suggestion = repository.get_by_id(suggestion_id)
    if not suggestion:
        return False, "Suggestion not found"

    if suggestion.get("status") == "applied":
        preferences_repo = PreferencesRepository(db)
        profile = _get_active_profile(preferences_repo)
        _remove_preference(
            profile,
            suggestion.get("action"),
            _normalize_phrase(suggestion.get("token", "")),
        )
        preferences_repo.upsert_profile(profile)

    if not repository.delete_by_id(suggestion_id):
        return False, "Suggestion not found"
    return True, "Suggestion permanently deleted"


def bulk_manage_profile_update_suggestions(
    db: Database, suggestion_ids: list[str], *, operation: str
) -> dict[str, int]:
    results = {"updated": 0, "deleted": 0, "skipped": 0}
    repository = ProfileUpdateSuggestionsRepository(db)

    for suggestion_id in dict.fromkeys(suggestion_ids):
        suggestion = repository.get_by_id(suggestion_id)
        if not suggestion:
            results["skipped"] += 1
            continue

        status = suggestion.get("status")
        changed = False
        if operation == "accept":
            if status in {"rejected", "reverted"}:
                repository.update_status(suggestion_id, "pending")
                changed, _ = apply_profile_update_suggestion(db, suggestion_id)
                if not changed:
                    repository.update_status(suggestion_id, status)
            elif status == "pending":
                changed, _ = apply_profile_update_suggestion(db, suggestion_id)
        elif operation == "reject":
            if status == "pending":
                changed = reject_profile_update_suggestion(db, suggestion_id)
            elif status == "applied":
                changed, _ = undo_profile_update_suggestion(db, suggestion_id)
                if changed:
                    repository.update_status(suggestion_id, "rejected")
        elif operation == "reopen":
            changed = reopen_profile_update_suggestion(db, suggestion_id)
        elif operation == "undo":
            changed, _ = undo_profile_update_suggestion(db, suggestion_id)
        elif operation == "delete":
            changed, _ = delete_profile_update_suggestion(db, suggestion_id)
            if changed:
                results["deleted"] += 1
                continue

        if changed:
            results["updated"] += 1
        else:
            results["skipped"] += 1

    return results


def _get_active_profile(preferences_repo: PreferencesRepository) -> dict[str, Any]:
    return preferences_repo.get_active_profile() or {
        "profile_name": "default",
        "active": True,
        "hard_avoids": [],
        "likes": [],
        "dislikes": [],
        "notes": "",
        "weights": {},
    }


def _remove_preference(profile: dict[str, Any], action: Any, token: str) -> None:
    field = "likes" if action == "add_like" else "dislikes"
    profile[field] = [
        item for item in profile.get(field, []) if _normalize_phrase(item) != token
    ]


def _add_preference(profile: dict[str, Any], action: str, token: str) -> None:
    target_field = "likes" if action == "add_like" else "dislikes"
    other_field = "dislikes" if target_field == "likes" else "likes"
    profile[other_field] = [
        item
        for item in profile.get(other_field, [])
        if _normalize_phrase(item) != token
    ]
    if token not in {_normalize_phrase(item) for item in profile.get(target_field, [])}:
        profile.setdefault(target_field, []).append(token)


def _resolve_target_recipe(
    *,
    event: dict[str, Any],
    recipes_repo: RecipesRepository,
    suggestions_repo: SuggestionsRepository,
) -> dict[str, Any] | None:
    target_type = event.get("target_type")
    target_id = event.get("target_id")
    if not target_id:
        return None

    if target_type == "recipe":
        return recipes_repo.get_by_id(target_id)
    if target_type == "suggestion":
        suggestion = suggestions_repo.get_by_id(target_id)
        if suggestion:
            return suggestion.get("recipe")
    return None


def _extract_tokens(recipe: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    metadata = recipe.get("metadata", {}) if isinstance(recipe, dict) else {}

    for tag in metadata.get("tags", []) if isinstance(metadata, dict) else []:
        clean = _normalize_phrase(tag)
        if _is_useful_phrase(clean):
            tokens.add(clean)

    for ingredient in recipe.get("ingredients", []) if isinstance(recipe, dict) else []:
        name = ""
        if isinstance(ingredient, dict):
            name = str(ingredient.get("ingredient", ""))
        elif isinstance(ingredient, str):
            name = ingredient
        clean = _normalize_ingredient_phrase(name)
        if _is_useful_phrase(clean):
            tokens.add(clean)

    return tokens


def _normalize_ingredient_phrase(value: Any) -> str:
    """Keep ingredient context while removing amounts and preparation wording."""
    text = str(value).lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    # Preparation notes are commonly separated from the ingredient by commas.
    text = re.split(r"[,;]", text, maxsplit=1)[0]
    words = _TOKEN_PATTERN.findall(text)
    words = [word for word in words if word not in _INGREDIENT_MODIFIERS]
    return " ".join(words)


def _normalize_phrase(value: Any) -> str:
    words = _TOKEN_PATTERN.findall(str(value).lower())
    return " ".join(words)


def _is_useful_phrase(phrase: str) -> bool:
    return bool(phrase and phrase not in _NON_SPECIFIC_PHRASES)
