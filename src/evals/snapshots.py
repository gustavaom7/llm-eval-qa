"""Machine-readable per-case reports and comparisons."""

import json
import os
from pathlib import Path

from support_bot.bot import Answer


def model_metadata() -> dict[str, str]:
    path = os.environ.get("OLLAMA_REPORT_METADATA")
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}


def write_snapshot(
    path: Path,
    mode: str,
    answers: dict[str, Answer],
    questions: dict[str, str],
    scores: dict[str, dict[str, float | None]],
    *,
    model_metadata: dict[str, str] | None = None,
) -> None:
    cases = {
        case_id: {
            "question": questions[case_id],
            "sources": answer.sources,
            "answer": answer.text,
            "scores": {metric: values[case_id] for metric, values in scores.items() if case_id in values},
            "latency_ms": answer.latency_ms,
        }
        for case_id, answer in answers.items()
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"schema_version": 1, "mode": mode, "model_metadata": model_metadata or {}, "cases": cases}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def compare_snapshots(before: Path, after: Path) -> str:
    previous, current = (json.loads(path.read_text(encoding="utf-8")) for path in (before, after))
    for report in (previous, current):
        if not isinstance(report, dict) or report.get("schema_version") != 1:
            raise ValueError("Expected a version 1 cases.json report.")
        if not isinstance(report.get("cases"), dict):
            raise ValueError("Report must contain a case mapping.")
    old, new = previous["cases"], current["cases"]
    lines = [f"Comparing {previous['mode']} with {current['mode']}"]
    if previous["mode"] != "live" or current["mode"] != "live":
        lines.append("Replay and record can report latencies from existing cassettes.")
    if previous["model_metadata"] != current["model_metadata"]:
        lines.append(f"Model runtime: {previous['model_metadata']} -> {current['model_metadata']}")
    if old == new:
        return "\n".join([*lines, "No case changes."])
    for case_id in sorted(old.keys() | new.keys()):
        if case_id not in old or case_id not in new:
            lines.append(f"{case_id}: {'added' if case_id in new else 'absent from the second report'}")
        elif old[case_id] != new[case_id]:
            lines.append(case_id)
            for field in ("question", "sources", "answer", "scores", "latency_ms"):
                left, right = old[case_id][field], new[case_id][field]
                if left != right:
                    lines.append(f"  {field}: {left!r} -> {right!r}")
    return "\n".join(lines)
