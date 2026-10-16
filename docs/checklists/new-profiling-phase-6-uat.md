# New Profiling Phase 6 UAT Checklist - Hardening, Telemetry, and Mitigations

Date: 16-Oct-26
Tester: hutch
Environment/Branch: .venv main
Mongo DB Name Used: RecipeLab

---

## 1) Preconditions

- [x] App is running at `http://localhost:3009`
- [x] `GET /api/health` responds successfully
- [x] At least one accepted tasting profile exists
- [x] At least one recipe exists in library

---

## 2) Provenance/Traceability Persistence

At `/profile`, generate or regenerate a tasting profile candidate.

- [x] Candidate renders with status + created timestamp
- [x] Candidate displays provider/model metadata
- [x] Candidate is persisted with `generation_run_id`
- [x] Candidate stores LLM provenance (`provider`, `model`, `prompt_text`, `raw_response`)
- [x] Candidate stores input snapshot (`dislikes`, `hard_avoids`, `recipe_ids`, `recipe_count`)

Optional DB check:

```bash
.venv/bin/python - <<'PY'
from app.config import AppConfig
from pymongo import MongoClient

cfg = AppConfig.from_env()
db = MongoClient(cfg.mongo_uri)[cfg.mongo_db_name]
doc = db["tasting_profiles"].find_one(sort=[("created_at", -1)])
print("id:", doc.get("_id"))
print("generation_run_id:", doc.get("generation_run_id"))
print("llm keys:", sorted((doc.get("llm") or {}).keys()))
print("input_snapshot keys:", sorted((doc.get("input_snapshot") or {}).keys()))
PY
```

---

## 3) Stale-Profile Indicator

With an accepted profile in place:

- [x] If recipe library changed since acceptance, warning appears on `/profile`
- [x] Warning includes added/removed recipe counts
- [x] If no changes, profile-current indicator appears
- [x] If historical profile lacks snapshot data, informational fallback message appears

---

## 4) Active-vs-Candidate Diff Summary

When both active profile and latest candidate exist:

- [x] Diff summary appears on `/profile`
- [x] Summary reports changed section count
- [x] Summary lists changed field names (or states match when unchanged)

---

## 5) Operational Error Messages

### Config failure
- [x] Misconfigured model/provider returns actionable generation error with missing fields called out

### LLM/provider failure
- [x] Failure message includes operation context + provider/model
- [x] Generation run is marked failed and still traceable by `run_id`

---

## 6) Automated Regression Checks

Run:

```bash
.venv/bin/python -m unittest tests.test_tasting_profile_service tests.test_web_routes tests.test_generate_api -v
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall app tests run.py
.venv/bin/python -m flake8 app tests
```

- [x] Targeted tests pass
- [x] Full test suite passes
- [x] Compile check passes
- [x] Lint check passes

---

## 7) Validation Gate Decision

Gate requirement: diagnostics and profile lifecycle mitigations are clear, reliable, and test-covered.

Overall Result:
- [x] PASS - Phase 6 complete
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
