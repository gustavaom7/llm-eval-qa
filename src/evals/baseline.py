"""Known findings: failures the team has reviewed and documented. CI fails on anything new."""

from __future__ import annotations

from pathlib import Path

import yaml

from evals.gates import GateResult


class BaselineError(ValueError):
    """The known-findings file breaks one of its rules."""


def load_known(path: Path) -> dict[str, dict[str, str]]:
    """Gate name -> item id -> why the failure is accepted (see docs/findings.md)."""
    known = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    for gate, items in known.items():
        for item_id, reason in (items or {}).items():
            if not str(reason or "").strip():
                raise BaselineError(f"{gate} / {item_id}: a known finding needs a reason")
    return {gate: dict(items or {}) for gate, items in known.items()}


def check_against_baseline(result: GateResult, known: dict[str, dict[str, str]]) -> None:
    """Pass when every failure is a known finding; fail on a new failure, or on a known finding that now
    passes (remove it from the baseline so it is guarded again)."""
    accepted = known.get(result.name, {})
    failing_ids = {failure.split(":", 1)[0] for failure in result.failures}
    new = [f for f in result.failures if f.split(":", 1)[0] not in accepted]
    fixed = sorted(set(accepted) - failing_ids)
    problems = []
    if not result.passed and new:
        problems.append(
            "New failure, not in datasets/known_findings.yaml:\n" + "\n".join(f"  - {f}" for f in new)
        )
    if fixed:
        problems.append(
            "Known finding now passes; remove it from datasets/known_findings.yaml: " + ", ".join(fixed)
        )
    assert not problems, result.message() + "\n" + "\n".join(problems)
