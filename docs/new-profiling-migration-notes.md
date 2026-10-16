# New Profiling Migration Notes (Existing Installs)

These notes cover migration from legacy feedback/profile-suggestion learning to the tasting-profile lifecycle.

## Summary of behavior changes

- Generation now requires an **accepted tasting profile**.
- Active profile editing is limited to **`dislikes`** and **`hard_avoids`**.
- Candidate tasting profiles are AI-generated, read-only, and must be accepted/rejected.
- Legacy `/feedback*` and `/profile/suggestions/*` routes are retired from active UX.

## Data compatibility

- Existing collections are kept for safety in first pass:
  - `feedback_events`
  - `profile_update_suggestions`
- They are not used by active profiling flow.

## Recommended rollout steps

1. Deploy code with new profiling phases (1–7).
2. Verify app startup and DB connectivity:
   - `/`
   - `/api/health`
3. Open `/profile`, save `dislikes` + `hard_avoids`, and generate a candidate profile.
4. Accept a candidate so generation is unblocked.
5. Validate `/generate` and `POST /api/generate` with accepted profile gate.

## Operational checks

- Ensure `LLM_PROVIDER` is set.
- Ensure model selection is valid (`LLM_MODEL` and/or runtime setting in `/settings`).
- Confirm candidate records include provenance fields (`llm.*`, `generation_run_id`, `input_snapshot`).

## Rollback note

No destructive migration is required for this phase. Legacy collections remain intact, so rollback is code-level (redeploy prior version) if needed.
