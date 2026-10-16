"""Deterministic gates: pure functions from answers to a pass/fail result a non-engineer can read."""

from __future__ import annotations

from dataclasses import dataclass

from evals.dataset import GoldenItem
from support_bot.bot import REFUSAL, Answer

MAX_LISTED = 10


@dataclass(frozen=True)
class GateResult:
    name: str
    value: float
    threshold: float
    passed: bool
    detail: str
    failures: list[str]
    unit: str = "rate"  # "rate" prints as a percentage, "tokens" as a count

    def message(self) -> str:
        gate = f"{self.threshold:.0f} tokens" if self.unit == "tokens" else f"{self.threshold:.0%}"
        lines = [f"{self.name}: {'PASS' if self.passed else 'FAIL'} — {self.detail}; gate {gate}"]
        lines += [f"  - {failure}" for failure in self.failures[:MAX_LISTED]]
        if len(self.failures) > MAX_LISTED:
            lines.append(f"  - … and {len(self.failures) - MAX_LISTED} more")
        return "\n".join(lines)


def _rate(passed: int, total: int) -> float:
    return passed / total if total else 1.0


def _normalise(text: str) -> str:
    """Lowercase, and treat hyphens and dashes as spaces: "7-day" matches "7 days", "5–10" matches "5-10"."""
    for dash in "-–—":
        text = text.replace(dash, " ")
    return " ".join(text.lower().split())


def _contains(text: str, phrase: str) -> bool:
    return _normalise(phrase) in _normalise(text)


def _in_scope(items: list[GoldenItem]) -> list[GoldenItem]:
    return [i for i in items if i.in_scope]


def retrieval_recall(
    items: list[GoldenItem], retrieved: dict[str, list[str]], threshold: float
) -> GateResult:
    scores, failures = [], []
    for item in _in_scope(items):
        got = retrieved[item.id]
        missing = [s for s in item.expected_sources if s not in got]
        scores.append(1 - len(missing) / len(item.expected_sources))
        if missing:
            failures.append(
                f"{item.id}: {', '.join(missing)} not in the top 3 (got {', '.join(got) or 'none'})"
            )
    value = sum(scores) / len(scores) if scores else 1.0
    detail = f"expected sources found in the top 3 for {value:.0%} of in-scope questions"
    return GateResult("Retrieval recall@3", value, threshold, value >= threshold, detail, failures)


def required_facts(items: list[GoldenItem], answers: dict[str, Answer], threshold: float) -> GateResult:
    scoped = _in_scope(items)
    failures = []
    complete = 0
    for item in scoped:
        missing = [f for f in item.must_include if not _contains(answers[item.id].text, f)]
        if missing:
            failures.append(f"{item.id}: missing {', '.join(repr(f) for f in missing)}")
        else:
            complete += 1
    value = _rate(complete, len(scoped))
    detail = f"{complete} of {len(scoped)} answers state every required fact"
    return GateResult("Required facts", value, threshold, value >= threshold, detail, failures)


def forbidden_claims(items: list[GoldenItem], answers: dict[str, Answer]) -> GateResult:
    failures = [
        f"{item.id}: says {claim!r}"
        for item in items
        for claim in item.must_not_include
        if _contains(answers[item.id].text, claim)
    ]
    offenders = len({f.split(":")[0] for f in failures})
    value = _rate(len(items) - offenders, len(items))
    detail = f"{offenders} of {len(items)} answers make a claim the policy rules out"
    return GateResult("Forbidden claims", value, 1.0, not failures, detail, failures)


def out_of_scope_refusal(items: list[GoldenItem], answers: dict[str, Answer]) -> GateResult:
    scoped = [i for i in items if not i.in_scope]
    failures = [
        f"{i.id}: answered instead of refusing: {answers[i.id].text[:80]!r}"
        for i in scoped
        if REFUSAL.lower() not in answers[i.id].text.lower()
    ]
    refused = len(scoped) - len(failures)
    value = _rate(refused, len(scoped))
    detail = f"{refused} of {len(scoped)} out-of-scope questions get the fixed refusal"
    return GateResult("Out-of-scope refusal", value, 1.0, not failures, detail, failures)


def citation(items: list[GoldenItem], answers: dict[str, Answer], threshold: float) -> GateResult:
    scoped = _in_scope(items)
    failures = []
    for item in scoped:
        a = answers[item.id]
        if not any(source in a.text for source in a.sources):
            failures.append(f"{item.id}: names none of {', '.join(a.sources) or '(no sources retrieved)'}")
    cited = len(scoped) - len(failures)
    value = _rate(cited, len(scoped))
    detail = f"{cited} of {len(scoped)} answers name a retrieved source"
    return GateResult("Citation", value, threshold, value >= threshold, detail, failures)


def input_tokens(answers: dict[str, Answer], max_tokens: int) -> GateResult:
    largest = max((a.input_tokens for a in answers.values()), default=0)
    failures = [
        f"{i}: {a.input_tokens} input tokens" for i, a in answers.items() if a.input_tokens > max_tokens
    ]
    detail = f"largest prompt is {largest} input tokens"
    return GateResult(
        "Input tokens per answer", largest, max_tokens, not failures, detail, failures, "tokens"
    )


def judge_mean(name: str, scores: dict[str, float | None], threshold: float) -> GateResult:
    failures = []
    for item_id, score in scores.items():
        if score is None:
            failures.append(f"{item_id}: judge output unreadable")
        elif score < threshold:
            failures.append(f"{item_id}: {score:.2f}")
    values = [0.0 if s is None else s for s in scores.values()]
    value = sum(values) / len(values) if values else 1.0
    detail = f"mean score {value:.2f} over {len(values)} judged answers"
    return GateResult(name, value, threshold, value >= threshold, detail, failures)
