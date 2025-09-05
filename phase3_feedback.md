# Phase 3 (Import & Telemetry) — Technical Review, Critique, and Enhancements

**Scope under review:** Fix import compatibility around `OpenAIScorer` → `OpenAITopicScorer`, and restore telemetry by adding a missing `record_metric()` to `TelemetryManager`.
**Goal:** Make changes robust, future‑proof, observable, and low‑risk.

---

## 1) Quick Verdict

- ✅ Your plan addresses the two reported breakages directly (import alias + missing method).
- ⚠️ The approach is **too narrow** and could reintroduce issues (alias drift, cyclic imports, vague metric semantics, state coupling).
- 🛠️ Add a **compatibility shim**, enforce **import discipline** in CI, and evolve telemetry to **structured, type‑safe metrics** with clear semantics.

---

## 2) Import Fixes — Critique & Better Patterns

### 2.1 Avoid relying solely on in‑file aliases
**Plan:** Add `OpenAIScorer = OpenAITopicScorer` in `openai_scorer.py` and export via `__all__`.
**Concerns:**
- Pollutes the public API and encourages indefinite use of the deprecated name.
- Masks unexpected imports and slows migration.

**Improved approach — compatibility shim + deprecation warning:**
- Create `openai_scorer_compat.py`:
  ```python
  # openai_scorer_compat.py
  import warnings
  from openai_scorer import OpenAITopicScorer as OpenAIScorer

  warnings.warn(
      "OpenAIScorer is deprecated; use OpenAITopicScorer from openai_scorer.",
      DeprecationWarning,
      stacklevel=2,
  )
  __all__ = ["OpenAIScorer"]
  ```
- For legacy paths, import from the shim:
  ```python
  from openai_scorer_compat import OpenAIScorer
  ```
- If you must keep an alias inside `openai_scorer.py`, gate it behind `ALLOW_LEGACY_OPENAI_SCORER_ALIAS=1` so it’s easy to remove later.

### 2.2 Eliminate import ambiguity in the codebase
- Replace all internal imports of the old name with `OpenAITopicScorer`.
- Prefer **absolute imports** (e.g., `from package.module import Name`) and avoid `sys.path.append` hacks.
- Add a CI test that **fails** if `from openai_scorer import OpenAIScorer` appears outside `tests/legacy_compat/` or `*_compat.py`.
- Run a lightweight **import cycle check** to catch regressions early.

### 2.3 Public API boundary & versioning
- Document in `CHANGELOG.md`: `OpenAIScorer` deprecated in next minor; removal in next major.
- Provide a stable public import (e.g., `from ai.scoring import TopicScorer`) via `ai/scoring/__init__.py` to decouple callers from file names.

---

## 3) Telemetry — Critique & Enhancements

### 3.1 Clarify `record_metric()` semantics
**Plan:** Add `record_metric()` that increments `current_run` fields based on name heuristics.
**Concerns:**
- Brittle string matching; unclear metric types; risk of silently wrong counts.

**Improved approach — a small, structured API with back‑compat:**
```python
# telemetry_manager.py (sketch)
class TelemetryManager:
    def record_counter(self, name: str, value: float = 1.0, labels: dict | None = None) -> None: ...
    def record_gauge(self,   name: str, value: float,       labels: dict | None = None) -> None: ...
    def record_histogram(self,name: str, value: float,       labels: dict | None = None) -> None: ...
    # Back-compat shim:
    def record_metric(self, name: str, value: float = 1.0, **labels) -> None:
        # Route via suffix convention (keeps Phase 3 small)
        # *.count -> counter, *.ms -> histogram, *.gauge -> gauge; default counter
        ...
```
- **Namespacing:** `pipeline.retries.count`, `openai.tokens_out.count`, `run.latency.ms`, `digest.items.count`.
- **Labels:** e.g., `{"db":"RSS","component":"scorer"}` with validation to prevent high cardinality.
- **Concurrency:** Avoid shared mutable state; ensure per‑process run data or thread‑safety.

### 3.2 Run headers & correlation
- Ensure each run has a **run_id** (UUID), present in logs and metrics labels.
- Persist **run headers** at start; finalize with wall time, totals, and status.

### 3.3 Output sinks & sampling
- Start with **structured JSON logs** for metrics (works even without a metrics backend):
  ```json
  {"ts":"...","evt":"metric","name":"openai.tokens_out.count","value":700,"labels":{"component":"scorer","run_id":"..."}}
  ```
- Add **sampling** (env‑tuned) for high‑volume events to keep logs lean.

### 3.4 Error/outcome taxonomy
- Standardize `outcome ∈ {OK, RETRY, FAIL, PARTIAL}` and emit a **final run summary** with counts per outcome.
- Label first error class and status (e.g., `error=RateLimitError`, `http=429`) for fast triage.

### 3.5 Telemetry tests
- Unit: verify routing of `record_metric()` to counter/gauge/histogram (table‑driven).
- Contract: `run headers` created before increments; finalized at end.
- Snapshot: JSON log schema (name/value/labels).
- Negative: guard against label cardinality explosions.

---

## 4) Concrete Code Adjustments

### 4.1 Minimal `record_metric()` with suffix routing (sketch)
```python
# telemetry_manager.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Final
import logging, time, uuid

log = logging.getLogger(__name__)

SUFFIX_TO_KIND: Final[dict[str, str]] = {".count":"counter",".ms":"histogram",".gauge":"gauge"}

@dataclass
class RunHeader:
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at_ms: int = field(default_factory=lambda: int(time.time()*1000))
    finished_at_ms: int | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    retries: int = 0
    failures: int = 0

class TelemetryManager:
    def __init__(self) -> None:
        self.current_run = RunHeader()

    def _emit(self, kind: str, name: str, value: float, labels: Dict[str,str] | None) -> None:
        rec = {"evt":"metric","kind":kind,"name":name,"value":value,"labels":labels or {},
               "run_id": self.current_run.run_id, "ts_ms": int(time.time()*1000)}
        log.info("METRIC %s", rec)

    def record_metric(self, name: str, value: float = 1.0, **labels) -> None:
        kind = next((k for s,k in SUFFIX_TO_KIND.items() if name.endswith(s)), "counter")
        self._emit(kind, name, value, labels)
        # Optional side effects for back-compat
        if name.endswith(".count") and "openai.tokens_out" in name:
            self.current_run.tokens_out += int(value)
        if name.endswith(".count") and "retries" in name:
            self.current_run.retries += int(value)
```

### 4.2 CI guard against legacy imports
```python
# tests/test_no_legacy_imports.py
import pathlib, re
LEGACY = re.compile(r"from\s+openai_scorer\s+import\s+OpenAIScorer\b")
def test_no_legacy_imports():
    root = pathlib.Path(__file__).resolve().parents[1]
    offenders = []
    for p in root.rglob("*.py"):
        if "tests" in p.parts or p.name.endswith("_compat.py"):
            continue
        if LEGACY.search(p.read_text(encoding="utf-8")):
            offenders.append(str(p))
    assert not offenders, f"Legacy import found in: {offenders}"
```

### 4.3 Lint/type hygiene
- Use `ruff` for import order/unused imports; `mypy` for types in telemetry/scorer.
- Ensure `__init__.py` exists across packages to avoid namespace confusion.

---

## 5) Acceptance Criteria (Phase 3)

- ✅ No runtime `ImportError` for legacy scorer paths; **compat shim in place**; all internal code uses `OpenAITopicScorer`.
- ✅ CI fails on legacy imports outside allowed locations.
- ✅ `TelemetryManager.record_metric()` exists and routes to counter/gauge/histogram via suffix convention.
- ✅ Run headers created at start, updated at end; logs include `run_id`, component, outcomes.
- ✅ Metrics/log lines are JSON‑structured, schema‑checked, and low‑cardinality.
- ✅ Unit + integration tests pass, including retry‑queue scenarios.
- ✅ `PHASED_REMEDIATION_TASKS.md` & `CHANGELOG.md` updated with deprecation and acceptance criteria.

---

## 6) Risk & Rollout

- **Risk:** Hidden external scripts still importing `OpenAIScorer` → Mitigate with shim + deprecation warnings.
- **Risk:** Metric cardinality explosion → Add label validation and sampling.
- **Rollout:**  
  1) Merge telemetry structure + shim (no behavior change).  
  2) Update internal imports to new class.  
  3) Enable CI guard that blocks legacy import.  
  4) Announce deprecation; remove shim in the next major.

---

## 7) Quick To‑Do Checklist

- [ ] Add `openai_scorer_compat.py` shim with deprecation warning.  
- [ ] Replace internal imports with `OpenAITopicScorer`; add CI guard against legacy imports.  
- [ ] Implement `record_metric()` with suffix routing + JSON structured logs.  
- [ ] Ensure `run_id` propagation and final run summary emission.  
- [ ] Add tests: imports, integration (retry queue), no‑legacy guard.  
- [ ] Update `PHASED_REMEDIATION_TASKS.md` & `CHANGELOG.md`.

---

## 8) Summary

Your fixes will resolve the immediate failures. The additions above keep the solution **safe, observable, and maintainable**: a temporary **compat shim** for imports, **CI‑enforced** migration off deprecated names, and **structured telemetry** that’s ready for future OpenTelemetry or metrics backends.
