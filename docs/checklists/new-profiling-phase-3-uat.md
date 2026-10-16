# New Profiling Phase 3 UAT Checklist - Profile UI Refresh

Date: 16-Oct-26
Tester: hutch
Environment/Branch: .venv main
Mongo DB Name Used: RecipeLab

---

## 1) Preconditions

- [x] App is running at `http://localhost:3009`
- [x] `GET /api/health` responds successfully
- [x] You can access `/profile`

---

## 2) Profile Inputs (Simplified)

- [x] `/profile` shows only profile inputs for **Dislikes** and **Hard Avoids**
- [x] Likes and Notes input fields are no longer shown in the profile form
- [x] Saving profile inputs persists dislikes/hard avoids correctly
- [x] Saving profile inputs does not re-introduce likes/notes behavior in UI

---

## 3) Candidate Generation / Regeneration

- [x] Clicking **Generate Tasting Profile** creates a candidate and returns to `/profile`
- [x] A success flash message appears after generation
- [x] Clicking **Regenerate Candidate** creates a fresh candidate and returns to `/profile`
- [x] Latest candidate card displays candidate status and JSON profile output

---

## 4) Candidate Review Actions

With a `candidate_pending` profile visible:

- [x] **Accept Candidate** marks it accepted
- [x] Accepted candidate becomes active profile
- [x] **Reject Candidate** marks pending candidate rejected
- [x] Reject does not overwrite active accepted profile

---

## 5) Read-Only Profile Displays

- [x] **Latest Candidate (Review Required)** section renders
- [x] **Active Accepted Tasting Profile** section renders
- [x] Both sections display read-only profile JSON text
- [x] If no accepted profile exists, warning message is shown

---

## 6) Responsive/Usability Checks

Test at `375x667`, `768x1024`, `1366x768`:

- [x] Generate/Regenerate/Accept/Reject buttons are usable
- [x] No horizontal overflow in profile cards
- [x] Long JSON content remains readable/scrollable

---

## 7) Automated Regression Checks

Run:

```bash
.venv/bin/python -m unittest tests.test_web_routes -v
.venv/bin/python -m unittest tests.test_tasting_profile_service -v
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall app tests run.py
```

- [x] Web route tests pass
- [x] Tasting profile service tests pass
- [x] Full test suite passes
- [x] Compile check passes

---

## 8) Validation Gate Decision

Gate requirement: profile UI supports read-only candidate review lifecycle (generate/regenerate/accept/reject) and simplified inputs.

Overall Result:
- [x] PASS - Phase 3 complete
- [ ] FAIL - remediation required

Notes / Issues Found:

```

```

Remediation Tasks (if any):

```

```

Sign-off:
- Name: hutch
- Date: 16-Oct-26
