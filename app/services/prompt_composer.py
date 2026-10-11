from __future__ import annotations

from typing import Any, Mapping


DEFAULT_HARD_CONSTRAINTS = [
    "whole chickpeas",
    "peanuts",
    "sprouts",
    "cauliflower",
    "cinnamon",
]


def compose_recipe_prompt(
    *,
    meal_type: str,
    instructions: str,
    profile: Mapping[str, Any] | None,
    hard_constraints: list[str] | None = None,
) -> str:
    profile = profile or {}
    constraints = hard_constraints or DEFAULT_HARD_CONSTRAINTS

    likes = ", ".join(profile.get("likes", [])) or "(none provided)"
    dislikes = ", ".join(profile.get("dislikes", [])) or "(none provided)"
    avoids = ", ".join(profile.get("hard_avoids", constraints))
    notes = profile.get("notes", "") or "(none provided)"
    user_instructions = instructions.strip() or "(none provided)"

    return (
        "Generate exactly one recipe as valid JSON only. No markdown, no extra prose.\n\n"
        f"Meal type: {meal_type}\n"
        f"User instructions: {user_instructions}\n\n"
        "Active tasting profile:\n"
        f"- likes: {likes}\n"
        f"- dislikes: {dislikes}\n"
        f"- hard avoids (strict): {avoids}\n"
        f"- notes: {notes}\n\n"
        "Hard requirements:\n"
        "- Respect all hard avoids strictly.\n"
        "- Keep difficulty practical for a home cook.\n"
        "- Include at least one clear protein source.\n"
        "- Keep method concise and sequential.\n\n"
        "Output JSON object schema:\n"
        "{\n"
        '  "title": "string",\n'
        '  "meal_type": "string",\n'
        '  "source": "AI Generated",\n'
        '  "servings": "string or number",\n'
        '  "prep_time": "string or number",\n'
        '  "cook_time": "string or number",\n'
        '  "rating": "string or number",\n'
        '  "difficulty": "string or number",\n'
        '  "tags": ["string"],\n'
        '  "ingredients": [{"quantity": "string", "unit": "string", "ingredient": "string"}],\n'
        '  "method": ["string"],\n'
        '  "notes": ["string"]\n'
        "}\n"
    )


def compose_canonical_conversion_prompt(
    *, meal_type: str, raw_recipe_text: str, allowed_tags: list[str] | None = None
) -> str:
    normalized_allowed_tags = [
        item.strip()
        for item in (allowed_tags or [])
        if isinstance(item, str) and item.strip()
    ]
    allowed_tags_line = (
        ", ".join(normalized_allowed_tags)
        if normalized_allowed_tags
        else "(none available)"
    )

    return (
        "Convert the raw recipe text into exactly one canonical recipe JSON object. "
        "Return valid JSON only. No markdown or extra prose.\n\n"
        f"Meal type to apply: {meal_type}\n\n"
        "Rules:\n"
        "- Preserve provided facts; do not invent missing metadata.\n"
        "- Keep missing values as empty strings or empty lists.\n"
        "- Normalize ingredients to objects with quantity, unit, ingredient.\n"
        "- Convert preparation headings into a simple method step list.\n\n"
        "Tag rules (strict):\n"
        f"- Allowed tags (existing library only): {allowed_tags_line}\n"
        "- Output tags must be selected only from the allowed list above.\n"
        "- If none fit, return an empty tags list.\n\n"
        "Output JSON schema:\n"
        "{\n"
        '  "title": "string",\n'
        '  "meal_type": "string",\n'
        '  "source": "string",\n'
        '  "servings": "string",\n'
        '  "prep_time": "string",\n'
        '  "cook_time": "string",\n'
        '  "rating": "string",\n'
        '  "difficulty": "string",\n'
        '  "tags": ["string"],\n'
        '  "ingredients": [{"quantity": "string", "unit": "string", "ingredient": "string"}],\n'
        '  "method": ["string"],\n'
        '  "notes": ["string"]\n'
        "}\n\n"
        "Raw recipe text to convert:\n"
        f"{raw_recipe_text.strip()}\n"
    )
