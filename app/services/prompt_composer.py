from __future__ import annotations

import json
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
    tasting_profile: Mapping[str, Any] | None = None,
    selected_recipes: list[Mapping[str, Any]] | None = None,
) -> str:
    if tasting_profile is not None:
        trimmed_instructions = instructions.strip()
        instructions_block = (
            f"User instructions:\n{trimmed_instructions}\n\n"
            if trimmed_instructions
            else ""
        )
        selected = [dict(item) for item in (selected_recipes or [])]
        selected_block = (
            "Reference recipes (JSON array, max 4):\n"
            f"{json.dumps(selected, ensure_ascii=False, indent=2)}\n\n"
            if selected
            else ""
        )

        return (
            "## Persona\n"
            "Act as an experienced recipe developer specialising in practical home cooking, balanced flavours, and personalised recipe recommendations.\n"
            "Create one original recipe that aligns with the user's tasting profile while still offering novelty.\n\n"
            "---\n\n"
            "## Task\n"
            "Generate exactly one recipe JSON object.\n"
            "Return JSON only. No Markdown, no prose outside JSON.\n\n"
            "---\n\n"
            "## Inputs\n\n"
            f"Requested meal type:\n{meal_type}\n\n"
            f"{instructions_block}"
            "Active tasting profile (JSON):\n"
            f"{json.dumps(dict(tasting_profile), ensure_ascii=False, indent=2)}\n\n"
            f"{selected_block}"
            "---\n\n"
            "## Rules\n"
            "1. Follow requested meal type exactly.\n"
            "2. Respect hard restrictions:\n"
            "   - Never include `hard_avoids_strict` ingredients.\n"
            "   - Avoid `explicit_dislikes` unless tasting profile explicitly permits a narrow exception.\n"
            "3. Use tasting profile as primary personalization source.\n"
            "4. If reference recipes are provided, use them as style/context signals only; do not copy.\n"
            "5. Ensure culinary coherence across ingredients, servings, timing, and method.\n"
            "6. Include at least one clear protein source consistent with profile and instructions.\n"
            "7. Method must be concise, sequential, and actionable.\n"
            "8. Every ingredient used in method must appear in ingredients list.\n"
            "9. Keep recipe practical for a home cook.\n"
            '10. For `rating`, return an empty string (`""`) because user rating is user-owned metadata.\n'
            '11. Set `source` to `"AI Generated"`.\n\n'
            "---\n\n"
            "## Output schema\n"
            "{\n"
            '  "title": "string",\n'
            '  "meal_type": "string",\n'
            '  "source": "AI Generated",\n'
            '  "servings": "string or number",\n'
            '  "prep_time": "string or number",\n'
            '  "cook_time": "string or number",\n'
            '  "rating": "",\n'
            '  "difficulty": "string or number",\n'
            '  "tags": ["string"],\n'
            '  "ingredients": [{"quantity": "string", "unit": "string", "ingredient": "string"}],\n'
            '  "method": ["string"],\n'
            '  "notes": ["string"]\n'
            "}\n"
        )

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


def compose_tasting_profile_prompt(
    *,
    dislikes: list[str],
    hard_avoids: list[str],
    current_tasting_profile: Mapping[str, Any] | None,
    user_recipes: list[Mapping[str, Any]],
) -> str:
    dislikes_json = json.dumps(dislikes, ensure_ascii=False)
    hard_avoids_json = json.dumps(hard_avoids, ensure_ascii=False)
    current_profile_json = json.dumps(
        dict(current_tasting_profile) if current_tasting_profile else None,
        ensure_ascii=False,
        indent=2,
    )
    recipes_json = json.dumps(
        [dict(item) for item in user_recipes], ensure_ascii=False, indent=2
    )

    return (
        "## Persona\n"
        "You are a food preference analyst and recommender-system designer.\n"
        "Infer this specific user's tasting profile from their own recipes and metadata, not from generic assumptions.\n"
        "Be evidence-based, conservative, and explicit about uncertainty.\n\n"
        "---\n\n"
        "## Task\n"
        "Generate exactly one tasting profile JSON object.\n"
        "Return JSON only. No Markdown, no prose outside JSON.\n\n"
        "---\n\n"
        "## Inputs\n\n"
        "Explicit user inputs:\n"
        f"- dislikes: {dislikes_json}\n"
        f"- hard_avoids: {hard_avoids_json}\n\n"
        "Current accepted tasting profile (if present, else null):\n"
        f"{current_profile_json}\n\n"
        "User recipes (structured JSON array):\n"
        f"{recipes_json}\n\n"
        "Each recipe may include:\n"
        "- meal_type\n"
        "- ingredients\n"
        "- method\n"
        "- metadata.servings\n"
        "- metadata.prep_time\n"
        "- metadata.cook_time\n"
        "- metadata.rating (1..10, may be empty)\n"
        "- metadata.difficulty (1..10, may be empty)\n"
        "- metadata.tags\n\n"
        "---\n\n"
        "## Rules\n"
        "1. Treat `hard_avoids` as strict constraints.\n"
        "2. Copy explicit `dislikes` into `explicit_dislikes`.\n"
        "3. Copy explicit `hard_avoids` into `hard_avoids_strict`.\n"
        "4. Weight evidence by both rating and frequency when possible.\n"
        "5. Distinguish strong vs moderate vs weak evidence in wording.\n"
        "6. If evidence is insufficient, state uncertainty explicitly.\n"
        "7. Do not invent personal facts not supported by input data.\n"
        "8. Use concise, concrete statements (no vague phrases like 'likes bold flavors').\n\n"
        "---\n\n"
        "## Output schema (return exactly this shape)\n"
        "{\n"
        '  "core_taste_preferences_global": ["string"],\n'
        '  "ingredient_protein_preferences": ["string"],\n'
        '  "flavour_cuisine_affinities": ["string"],\n'
        '  "texture_dish_type_preferences": ["string"],\n'
        '  "cooking_behaviour_constraints": ["string"],\n'
        '  "meal_context_modifiers": {\n'
        '    "main": ["string"],\n'
        '    "lunch_batch": ["string"],\n'
        '    "lunch_single": ["string"],\n'
        '    "breakfast": ["string"],\n'
        '    "dessert": ["string"]\n'
        "  },\n"
        '  "explicit_dislikes": ["string"],\n'
        '  "hard_avoids_strict": ["string"],\n'
        '  "inferred_avoidance_signals_red_flags": ["string"],\n'
        '  "ideal_constraints_for_new_suggestions": ["string"],\n'
        '  "known_uncertainties_data_gaps": ["string"],\n'
        '  "evidence_summary": {\n'
        '    "recipe_count_used": 0,\n'
        '    "high_rating_threshold": 8,\n'
        '    "low_rating_threshold": 4,\n'
        '    "notes": "string"\n'
        "  }\n"
        "}\n"
    )
