# New Profiling Plan (AI Tasting Profile Workflow)

## 1) Confirmed Requirements (Locked)

This plan reflects the clarified product direction:

1. The user manages only **dislikes** and **hard avoids** on `/profile`.
2. The tasting profile is **read-only** (AI-generated), but the user can:
   - view it,
   - **accept** it,
   - **reject** it,
   - **regenerate** it.
3. Remove per-recipe/suggestion feedback controls (`liked`, `disliked`, `note`).
4. Remove profile suggestion workflow (token accept/reject/reopen/undo).
5. Build tasting profile from:
   - explicit dislikes + hard avoids,
   - existing recipes (including metadata, especially rating).
6. Recipe generation must use:
   - requested meal type,
   - optional user instructions,
   - optional up to 4 selected recipes,
   - accepted tasting profile.
7. If no accepted tasting profile exists, `/generate` must block and direct user to create one.

---

## 2) Target UX and Runtime Behavior

## 2.1 `/profile`

- Inputs:
  - `dislikes` (multiline)
  - `hard_avoids` (multiline)
- Actions:
  - `Generate tasting profile`
  - `Regenerate candidate`
  - `Accept candidate`
  - `Reject candidate`
- Read-only profile display:
  - current accepted profile
  - latest candidate profile
  - status and timestamps

## 2.2 `/generate`

- Inputs:
  - `meal_type`
  - optional `instructions`
  - optional recipe selector (0..4 recipes)
- Precondition:
  - accepted tasting profile exists; otherwise show blocking warning + link to `/profile`.

## 2.3 Acceptance state model

- A generated profile starts as `candidate_pending`.
- `accept`:
  - marks candidate as accepted + active,
  - marks previous active profile as `superseded`.
- `reject`:
  - marks candidate rejected,
  - leaves current active profile unchanged.
- Generation always uses the **active accepted** profile.

---

## 3) Concrete Field-Level Schema

## 3.1 Collection: `tasting_profiles`

```json
{
  "_id": "ObjectId",
  "status": "candidate_pending | accepted | rejected | superseded",
  "is_active": true,

  "profile": {
    "core_taste_preferences_global": ["string"],
    "ingredient_protein_preferences": ["string"],
    "flavour_cuisine_affinities": ["string"],
    "texture_dish_type_preferences": ["string"],
    "cooking_behaviour_constraints": ["string"],
    "meal_context_modifiers": {
      "main": ["string"],
      "lunch_batch": ["string"],
      "lunch_single": ["string"],
      "breakfast": ["string"],
      "dessert": ["string"]
    },
    "explicit_dislikes": ["string"],
    "hard_avoids_strict": ["string"],
    "inferred_avoidance_signals_red_flags": ["string"],
    "ideal_constraints_for_new_suggestions": ["string"],
    "known_uncertainties_data_gaps": ["string"],
    "evidence_summary": {
      "recipe_count_used": 0,
      "high_rating_threshold": 8,
      "low_rating_threshold": 4,
      "notes": "string"
    }
  },

  "input_snapshot": {
    "dislikes": ["string"],
    "hard_avoids": ["string"],
    "recipe_ids": ["string"],
    "recipe_count": 0
  },

  "llm": {
    "provider": "string",
    "model": "string",
    "endpoint": "string",
    "prompt_template": "tasting_profile_v1",
    "prompt_text": "string",
    "raw_response": "string",
    "error": "string"
  },

  "review": {
    "decision": "pending | accepted | rejected",
    "decision_note": "string",
    "decided_at": "datetime"
  },

  "generation_run_id": "string",
  "created_at": "datetime",
  "updated_at": "datetime",
  "accepted_at": "datetime",
  "rejected_at": "datetime",
  "superseded_at": "datetime"
}
```

### Required fields

- Top-level required on insert:
  - `status`, `is_active`, `profile`, `input_snapshot`, `llm`, `review`, `created_at`, `updated_at`
- Additional required by status:
  - `accepted`: `accepted_at`, `review.decision=accepted`, `is_active=true`
  - `rejected`: `rejected_at`, `review.decision=rejected`, `is_active=false`
  - `candidate_pending`: `review.decision=pending`, `is_active=false`

### Indexes

1. `tasting_profiles_status_created_at` on `(status ASC, created_at DESC)`
2. `tasting_profiles_is_active_unique` unique partial index where `is_active=true`
3. `tasting_profiles_generation_run_id` on `(generation_run_id ASC)`

---

## 4) Cleaned Production Prompts (Drop-In Ready)

These templates are production-safe (JSON-only output, valid schema, consistent keys).

## 4.1 `prompts/tasting-profile-ai-prompt.md`

```md
## Persona
You are a food preference analyst and recommender-system designer.
Infer this specific user’s tasting profile from their own recipes and metadata, not from generic assumptions.
Be evidence-based, conservative, and explicit about uncertainty.

---

## Task
Generate exactly one tasting profile JSON object.
Return JSON only. No Markdown, no prose outside JSON.

---

## Inputs

Explicit user inputs:
- dislikes: {{USER_DISLIKES_JSON_ARRAY}}
- hard_avoids: {{USER_HARD_AVOIDS_JSON_ARRAY}}

Current accepted tasting profile (if present, else null):
{{CURRENT_TASTING_PROFILE_JSON_OR_NULL}}

User recipes (structured JSON array):
{{USER_RECIPES_JSON_ARRAY}}

Each recipe may include:
- meal_type
- ingredients
- method
- metadata.servings
- metadata.prep_time
- metadata.cook_time
- metadata.rating (1..10, may be empty)
- metadata.difficulty (1..10, may be empty)
- metadata.tags

---

## Rules
1. Treat `hard_avoids` as strict constraints.
2. Copy explicit `dislikes` into `explicit_dislikes`.
3. Copy explicit `hard_avoids` into `hard_avoids_strict`.
4. Weight evidence by both rating and frequency when possible.
5. Distinguish strong vs moderate vs weak evidence in wording.
6. If evidence is insufficient, state uncertainty explicitly.
7. Do not invent personal facts not supported by input data.
8. Use concise, concrete statements (no vague phrases like “likes bold flavors”).

---

## Output schema (return exactly this shape)
{
  "core_taste_preferences_global": ["string"],
  "ingredient_protein_preferences": ["string"],
  "flavour_cuisine_affinities": ["string"],
  "texture_dish_type_preferences": ["string"],
  "cooking_behaviour_constraints": ["string"],
  "meal_context_modifiers": {
    "main": ["string"],
    "lunch_batch": ["string"],
    "lunch_single": ["string"],
    "breakfast": ["string"],
    "dessert": ["string"]
  },
  "explicit_dislikes": ["string"],
  "hard_avoids_strict": ["string"],
  "inferred_avoidance_signals_red_flags": ["string"],
  "ideal_constraints_for_new_suggestions": ["string"],
  "known_uncertainties_data_gaps": ["string"],
  "evidence_summary": {
    "recipe_count_used": 0,
    "high_rating_threshold": 8,
    "low_rating_threshold": 4,
    "notes": "string"
  }
}
```

## 4.2 `prompts/recipe_suggestion_prompt-v2.md`

```md
## Persona
Act as an experienced recipe developer specialising in practical home cooking, balanced flavours, and personalised recipe recommendations.
Create one original recipe that aligns with the user’s tasting profile while still offering novelty.

---

## Task
Generate exactly one recipe JSON object.
Return JSON only. No Markdown, no prose outside JSON.

---

## Inputs

Requested meal type:
{{MEAL_TYPE}}

{{OPTIONAL_USER_INSTRUCTIONS_BLOCK}}

Active tasting profile (JSON):
{{TASTING_PROFILE_JSON}}

{{OPTIONAL_SELECTED_RECIPES_BLOCK_MAX_4}}

Where optional blocks are:
- If user instructions exist:
  User instructions:
  {{USER_INSTRUCTIONS}}
- If selected recipes exist (1..4):
  Reference recipes (JSON array, max 4):
  {{SELECTED_RECIPES_JSON_ARRAY}}

---

## Rules
1. Follow requested meal type exactly.
2. Respect hard restrictions:
   - Never include `hard_avoids_strict` ingredients.
   - Avoid `explicit_dislikes` unless tasting profile explicitly permits a narrow exception.
3. Use tasting profile as primary personalization source.
4. If reference recipes are provided, use them as style/context signals only; do not copy.
5. Ensure culinary coherence across ingredients, servings, timing, and method.
6. Include at least one clear protein source consistent with profile and instructions.
7. Method must be concise, sequential, and actionable.
8. Every ingredient used in method must appear in ingredients list.
9. Keep recipe practical for a home cook.
10. For `rating`, return an empty string (`""`) because user rating is user-owned metadata.
11. Set `source` to `"AI Generated"`.

---

## Output schema
{
  "title": "string",
  "meal_type": "string",
  "source": "AI Generated",
  "servings": "string or number",
  "prep_time": "string or number",
  "cook_time": "string or number",
  "rating": "",
  "difficulty": "string or number",
  "tags": ["string"],
  "ingredients": [{"quantity": "string", "unit": "string", "ingredient": "string"}],
  "method": ["string"],
  "notes": ["string"]
}
```

---

## 5) Clarification Assessment

Your clarification is strong and coherent.

Benefits over current system:
- Much simpler UX.
- Removes abstract token moderation that lacked context.
- Uses richer evidence (entire recipe corpus + ratings metadata).

Design consequences to enforce:
- A formal candidate/accept/reject lifecycle for tasting profiles.
- Strict generation gate (no accepted profile => no generation).
- Clear audit trail (prompt, model, input snapshot, raw response).

---

## 6) Ready-to-Go Phased Implementation Plan

Each phase includes engineering tasks, automated tests, and user validation gate.

## Phase 0 — Contract + Prompt + Schema Lock

### Build
- Finalize `tasting_profiles` schema and status transitions.
- Approve both cleaned prompt templates.
- Define canonical serialization helpers for recipe snippets and profile JSON.

### Automated testing
- Add schema/unit tests for new normalization helpers (if added now).
- Add prompt-composer snapshot tests for placeholders and optional blocks.

### User validation
- Review and approve:
  - profile JSON shape,
  - accept/reject/regenerate behavior,
  - generation gating rule.

### Exit criteria
- No unresolved ambiguity in data model or prompt contracts.

---

## Phase 1 — Data Layer (Repositories + Indexes)

### Build
- Add `TastingProfilesRepository`.
- Add indexes listed above.
- Add read/write/query methods:
  - create candidate
  - get active accepted
  - get latest candidate
  - accept candidate (transaction-like sequence)
  - reject candidate

### Automated testing
- Repository tests for create/read/status transitions.
- Index tests including active-profile uniqueness behavior.

### User validation
- Confirm profile records are persisted and statuses look correct in DB.

### Exit criteria
- Repository contract stable and fully tested.

---

## Phase 2 — Tasting Profile Generation Service

### Build
- Add service: `generate_tasting_profile_candidate(db, regenerate=False)`.
- Gather inputs from:
  - `preferences` (dislikes/hard_avoids)
  - `recipes` collection (active library)
  - current accepted profile (optional)
- Compose and send tasting-profile prompt via `LLMAdapter`.
- Parse/validate AI response against profile schema.
- Persist candidate in `tasting_profiles`.
- Log prompt/raw response/run status for traceability.

### Automated testing
- Service success path with mocked adapter.
- Invalid JSON / invalid schema handling.
- Ensure explicit dislikes/hard avoids are preserved in stored profile.

### User validation
- Generate candidate and inspect readability/quality on real data.

### Exit criteria
- Reliable candidate generation with robust failure paths.

---

## Phase 3 — Profile UI Refresh (Read-Only + Review Workflow)

### Build
- Simplify `/profile` form to only dislikes + hard avoids.
- Add candidate panel with read-only JSON/sections.
- Add actions:
  - Generate
  - Regenerate
  - Accept
  - Reject
- Show active accepted profile and latest candidate status.

### Automated testing
- Web route tests for each profile action.
- Template rendering tests for states:
  - no candidate,
  - pending candidate,
  - accepted active profile,
  - rejected candidate.

### User validation
- Manual UAT: create candidate, reject, regenerate, accept.

### Exit criteria
- Profile lifecycle works end-to-end in UI.

---

## Phase 4 — Generation Flow Update (Profile Gate + 4 Recipe Selector)

### Build
- Update `/generate` UI:
  - instructions
  - multi-select recipe picker (max 4)
- Update generation service signature to accept selected recipe IDs.
- Resolve selected recipes and embed as optional prompt block.
- Enforce precondition: accepted profile must exist.
- If no profile: block and redirect to `/profile` with clear guidance.

### Automated testing
- Route tests:
  - blocked generation without accepted profile,
  - valid generation with profile,
  - selection count >4 rejected.
- Prompt tests:
  - optional recipe block omitted when none selected,
  - included when selected.

### User validation
- UAT with 0, 1, and 4 selected recipes.
- Validate generation quality and personalization.

### Exit criteria
- New generation path stable and gated correctly.

---

## Phase 5 — Remove Legacy Profiling and Feedback Workflows

### Build
- Remove/disable routes and template sections for:
  - `/feedback*`
  - profile update suggestion actions
- Remove runtime dependencies on:
  - `profile_refinement_service`
  - `ProfileUpdateSuggestionsRepository`
  - `FeedbackEventsRepository` in active web flows
- Update imports and `ensure_all_indexes` wiring.
- Keep migration safe: do not hard-delete historical collections in first pass.

### Automated testing
- Remove/replace obsolete tests.
- Add regression tests ensuring no broken links/forms remain.

### User validation
- Navigate all key pages and confirm old controls are gone.

### Exit criteria
- Legacy profiling/feedback paths fully retired from UX and active code paths.

---

## Phase 6 — Hardening, Telemetry, and Mitigations

### Build
- Persist provenance and traceability fields for profile generation.
- Add stale-profile indicator (e.g., recipe library changed since acceptance).
- Add lightweight diff summary between active profile and latest candidate.
- Improve operational error messages for provider/model/config failures.

### Automated testing
- Tests for stale detection logic and provenance persistence.
- Failure-mode tests for LLM and parsing errors.

### User validation
- Confirm stale warnings and regeneration flow are understandable.

### Exit criteria
- Reliable diagnostics and maintainable profile lifecycle.

---

## Phase 7 — Documentation + Release Validation

### Build
- Update docs:
  - `docs/taste-profiling.md`
  - `docs/ARCHITECTURE_REFERENCE.md`
  - relevant UAT checklists
- Add migration notes for existing installs.

### Automated testing
- Full test suite pass.
- Manual smoke tests: `/`, `/profile`, `/generate`, `/suggestions`, `/recipes`, `/api/health`, `/api/generate`.

### User validation
- Sign-off session using real workflows and quality checks.

### Exit criteria
- Release-ready with updated documentation and accepted UAT.

---

## 7) Risk Controls (Mitigations Agreed)

1. **LLM dependence risk**
   - Store prompt/raw response/model metadata for each profile generation.
2. **Profile drift/staleness risk**
   - Show stale indicator when recipe corpus changes materially.
3. **Inference quality risk**
   - Keep explicit dislikes/hard avoids authoritative and always copied through.
4. **Regression risk**
   - Phase-by-phase test gates and user validation before advancing.

---

## 8) Immediate Next Step

Start with **Phase 0** and produce implementation-ready tasks/issues from this document before touching runtime behavior.
