# Taste Profiling Guide (Current Workflow)

RecipeLab now uses an **AI-generated tasting profile** lifecycle. Legacy feedback/profile-suggestion controls are retired from active UX.

---

## 1) Inputs That Affect Generation

| Input | Where set | Effective weight | Notes |
|---|---|---|---|
| Meal type | `/generate`, `POST /api/generate` | Hard constraint | Invalid meal types are rejected. |
| Accepted tasting profile | `/profile` (accept candidate) | Hard gate + strong context | Generation is blocked until an accepted profile exists. |
| Hard avoids | `/profile` | Strict constraint | User-authored and always copied through into generated profile. |
| Dislikes | `/profile` | Strong context | User-authored and always copied through into generated profile. |
| Instructions | `/generate` / API `instructions` | High soft influence | Optional free text per run. |
| Reference recipes (up to 4) | `/generate` / API `reference_recipe_ids` | Medium-high soft influence | Used as optional style/taste anchors. |
| Model selection | `/settings` or API `model` override | Model behavior influence | Controls model used for that run. |

---

## 2) Profile Lifecycle

Collection: `tasting_profiles`

Statuses:
- `candidate_pending`
- `accepted`
- `rejected`
- `superseded`

Rules:
- At most one active accepted profile.
- Accepting a candidate supersedes the previous active accepted profile.
- Candidate/active profile content is read-only AI output in the UI.

---

## 3) Generation Gate

Generation is blocked without an accepted tasting profile:

- Web (`/generate`) shows a clear prompt to create/accept profile first.
- API (`POST /api/generate`) returns a validation error.

---

## 4) Mitigations and Diagnostics

Phase 6 hardening includes:

- **Provenance/traceability** on each generated candidate:
  - `generation_run_id`
  - `llm.provider`, `llm.model`, `llm.prompt_text`, `llm.raw_response`
  - `input_snapshot` (dislikes/hard_avoids/recipe IDs/count)
- **Stale-profile indicator** when recipe library changed since acceptance.
- **Candidate-vs-active diff summary** to show what changed before accepting.
- **Improved operational errors** for missing provider/model and provider/model-specific LLM failures.

---

## 5) API Notes

`POST /api/generate` supports:

- `meal_type` (required)
- `instructions` (optional)
- `reference_recipe_ids` (optional, max 4)
- `model` (optional override)

Requires an accepted tasting profile.

---

## 6) What Is Retired from Active UX

- Per-recipe/per-suggestion feedback actions (`/feedback*`)
- Profile update suggestion action routes (`/profile/suggestions/*`)
- Prompt influence via legacy likes/notes suggestion pipeline

Historical collections may still exist for migration safety, but are not part of active profiling flow.
