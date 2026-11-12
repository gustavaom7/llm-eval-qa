"""Known findings: failures the team has reviewed and documented. CI fails on anything new."""

from __future__ import annotations

import warnings
from pathlib import Path

import yaml

from evals.gates import GateResult

NEVER_ACCEPTED = ("Critical failures", "Critical failures (red-team)")  # spec: 0 critical, no exceptions


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


def baseline_decision(
    result: GateResult, known: dict[str, dict[str, str]], *, live: bool = False
) -> tuple[str, list[str]]:
    """Return the CI decision and any details needed to review it."""
    accepted = known.get(result.name, {})
    if result.name in NEVER_ACCEPTED and accepted:
        return "Blocked", [f"{result.name} cannot be accepted as known findings: the gate is always 0."]
    failing_ids = {failure.split(":", 1)[0] for failure in result.failures}
    new = [f for f in result.failures if f.split(":", 1)[0] not in accepted]
    fixed = sorted(set(accepted) - failing_ids)
    problems = []
    if not result.passed and new:
        problems.append(
            "New failure, not in datasets/known_findings.yaml:\n" + "\n".join(f"  - {f}" for f in new)
        )
    if not result.passed and not result.failures:
        problems.append("Gate did not meet its threshold.")
    if fixed and not live:
        problems.append(
            "Known finding now passes; remove it from datasets/known_findings.yaml: " + ", ".join(fixed)
        )
    if problems:
        return "Blocked", problems
    if fixed:
        return "Review improvement", [
            f"{result.name}: known finding passed live; review against the recording: {', '.join(fixed)}"
        ]
    return ("Passed" if result.passed else "Accepted finding"), []


def check_against_baseline(
    result: GateResult, known: dict[str, dict[str, str]], *, live: bool = False
) -> None:
    status, details = baseline_decision(result, known, live=live)
    if status == "Review improvement":
        warnings.warn(details[0], stacklevel=2)
    assert status != "Blocked", result.message() + "\n" + "\n".join(details)
