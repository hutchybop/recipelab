# New Profiling Phase 1 UAT Checklist - Data Layer (tasting_profiles)

Date: 16-Oct-26
Tester: hutch
Environment/Branch: .venv, main
Mongo DB Name Used: RecipeLab

---

## 1) Preconditions

- [x] App dependencies installed and tests runnable.
- [x] MongoDB is reachable for this environment.
- [x] New profiling plan document exists: `docs/new_profiling_plan.md`.

---

## 2) Scope of this Phase (What should be true)

- [x] `tasting_profiles` repository exists and is wired in repository exports.
- [x] Index bootstrap includes `tasting_profiles` indexes.
- [x] Repository supports candidate create, latest candidate lookup, accept, reject, and active-profile lookup.
- [x] Acceptance supersedes previous active accepted profile.

---

## 3) Automated Checks

Run:

```bash
.venv/bin/python -m unittest tests.test_repositories tests.test_indexes -v
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall app tests run.py
```

- [x] Repository/index targeted tests pass.
- [x] Full test suite passes.
- [x] Compile check passes.

---

## 4) Manual Data Validation (Mongo)

Validate with Mongo shell/Compass using a test DB.

### 4.1 Candidate creation
- [x] Create a candidate tasting profile record through repository/service test harness.
- [x] Confirm stored values:
  - `status = candidate_pending`
  - `is_active = false`
  - `review.decision = pending`
  - `created_at` and `updated_at` are present.

### 4.2 Accept flow
- [x] Accept candidate A.
- [x] Confirm candidate A becomes:
  - `status = accepted`
  - `is_active = true`
  - `accepted_at` set
  - `review.decision = accepted`.

### 4.3 Supersede flow
- [x] Create candidate B and accept it.
- [x] Confirm candidate B is now active accepted profile.
- [x] Confirm candidate A changed to:
  - `status = superseded`
  - `is_active = false`
  - `superseded_at` set.

### 4.4 Reject flow
- [x] Create candidate C and reject it.
- [x] Confirm candidate C becomes:
  - `status = rejected`
  - `is_active = false`
  - `rejected_at` set
  - `review.decision = rejected`.

---

## 5) Index Validation

- [x] Collection `tasting_profiles` has index `tasting_profiles_status_created_at`.
- [x] Collection `tasting_profiles` has index `tasting_profiles_is_active_unique`.
- [x] Collection `tasting_profiles` has index `tasting_profiles_generation_run_id`.

---

## 6) Validation Gate Decision

Gate requirement: data layer is stable and ready for Phase 2 service integration.

Overall Result:
- [x] PASS - Phase 1 complete
- [ ] FAIL - remediation required

Notes / Issues Found:

```

```

Remediation Tasks (if any):

```

```

Sign-off:
- Name: Hutch
- Date: 16-Oct-26
