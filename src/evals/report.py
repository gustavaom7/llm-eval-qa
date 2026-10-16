"""The run summary: gate results and model latencies, as Markdown for the CI job summary."""

from __future__ import annotations

import math
from pathlib import Path

from evals.gates import GateResult


def _percentile(values: list[int], p: float) -> int:
    ordered = sorted(values)
    return ordered[max(math.ceil(p / 100 * len(ordered)) - 1, 0)]  # nearest rank


def _format(result: GateResult, value: float) -> str:
    return f"{value:.0f}" if result.unit == "tokens" else f"{value:.0%}"


def write_summary(path: Path, gates: list[GateResult], latencies_ms: dict[str, list[int]], mode: str) -> None:
    lines = [
        f"# Evaluation summary ({mode})",
        "",
        "| Gate | Result | Value | Threshold |",
        "|---|---|---|---|",
    ]
    for g in gates:
        result = "PASS" if g.passed else "FAIL"
        lines.append(f"| {g.name} | {result} | {_format(g, g.value)} | {_format(g, g.threshold)} |")
    failing = [g for g in gates if not g.passed]
    if failing:
        lines += ["", "## Failures", "", "```", *(g.message() for g in failing), "```"]
    timed = {model: values for model, values in latencies_ms.items() if values}
    if timed:
        lines += ["", "| Model | Calls | p50 ms | p95 ms | Total min |", "|---|---|---|---|---|"]
        for model, values in timed.items():
            total_min = sum(values) / 60_000
            lines.append(
                f"| {model} | {len(values)} | {_percentile(values, 50)} | {_percentile(values, 95)} "
                f"| {total_min:.1f} |"
            )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
