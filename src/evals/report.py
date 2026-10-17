"""The run summary: gate results and model latencies, as Markdown for the CI job summary."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from evals.gates import GateResult, percentile

# (attack id, vulnerability, technique, refused with the fixed sentence)
AttackRow = tuple[str, str, str, bool]


def _flatten(budgets: dict, prefix: str = "") -> list[tuple[str, object]]:
    rows = []
    for key, value in budgets.items():
        if isinstance(value, dict):
            rows += _flatten(value, f"{prefix}{key}.")
        else:
            rows.append((f"{prefix}{key}", value))
    return rows


def _red_team(attacks: list[AttackRow], gates: list[GateResult]) -> list[str]:
    critical = next((g for g in gates if g.name == "Critical failures (red-team)"), None)
    critical_ids = {f.split(":", 1)[0] for f in critical.failures} if critical else set()
    by_vulnerability: dict[str, list[AttackRow]] = defaultdict(list)
    for row in attacks:
        by_vulnerability[row[1]].append(row)
    lines = [
        "",
        "## Red-team",
        "",
        "| Vulnerability | Attacks | Refused | Answered | Critical |",
        "|---|---|---|---|---|",
    ]
    for vulnerability, rows in sorted(by_vulnerability.items()):
        refused = sum(r[3] for r in rows)
        critical_count = sum(r[0] in critical_ids for r in rows)
        lines.append(
            f"| {vulnerability} | {len(rows)} | {refused} | {len(rows) - refused} | {critical_count} |"
        )
    return lines


def _format(result: GateResult, value: float) -> str:
    return f"{value:.0%}" if result.unit == "rate" else f"{value:.0f}"


def write_summary(
    path: Path,
    gates: list[GateResult],
    latencies_ms: dict[str, list[int]],
    mode: str,
    budgets: dict | None = None,
    known: dict[str, dict[str, str]] | None = None,
    attacks: list[AttackRow] | None = None,
) -> None:
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
                f"| {model} | {len(values)} | {percentile(values, 50)} | {percentile(values, 95)} "
                f"| {total_min:.1f} |"
            )
    if attacks:
        lines += _red_team(attacks, gates)
    if known:
        lines += ["", "## Known findings", "", "| Gate | Item | Why it is accepted |", "|---|---|---|"]
        lines += [
            f"| {gate} | {item} | {why} |" for gate, items in known.items() for item, why in items.items()
        ]
    if budgets:
        lines += ["", "## Budgets in force", "", "| Budget | Value |", "|---|---|"]
        lines += [f"| {key} | {value} |" for key, value in _flatten(budgets)]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
