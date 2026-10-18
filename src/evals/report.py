"""The run summary: gate results and model latencies, as Markdown for the CI job summary."""

from __future__ import annotations

from collections import defaultdict
from html import escape
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


CSS = """
:root { --bg:#ffffff; --fg:#1b1f24; --muted:#5b636e; --line:#d8dde3; --pass:#1a7f37; --fail:#cf222e;
  --chip:#f3f5f7; }
@media (prefers-color-scheme: dark) { :root { --bg:#0d1117; --fg:#e6edf3; --muted:#9aa4af; --line:#30363d;
  --pass:#3fb950; --fail:#f85149; --chip:#161b22; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }
main { max-width: 960px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 1.6rem; margin: 0 0 4px; } h2 { font-size: 1.15rem; margin: 32px 0 8px; }
p.meta { color: var(--muted); margin: 0 0 16px; }
.scroll { overflow-x: auto; } table { border-collapse: collapse; width: 100%; font-size: .95rem; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--muted); font-weight: 600; } td.num { font-variant-numeric: tabular-nums; }
.status { font-weight: 700; padding: 2px 8px; border-radius: 999px; background: var(--chip); }
.PASS { color: var(--pass); } .FAIL { color: var(--fail); }
pre { background: var(--chip); padding: 12px; border-radius: 8px; overflow-x: auto; white-space: pre-wrap; }
a { color: inherit; }
"""


def _table(headers: list[str], rows: list[list[str]], numeric: set[int] = frozenset()) -> str:
    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body = "".join(
        "<tr>"
        + "".join(f'<td class="num">{c}</td>' if i in numeric else f"<td>{c}</td>" for i, c in enumerate(r))
        + "</tr>"
        for r in rows
    )
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def write_html(
    path: Path,
    gates: list[GateResult],
    latencies_ms: dict[str, list[int]],
    mode: str,
    budgets: dict | None = None,
    known: dict[str, dict[str, str]] | None = None,
    attacks: list[AttackRow] | None = None,
    run_label: str = "",
) -> None:
    """The same report as write_summary, as one static HTML page (no scripts, no external assets)."""
    parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>llm-eval-qa report</title>",
        f"<style>{CSS}</style></head><body><main>",
        "<h1>Lumen+ support bot: evaluation report</h1>",
        f'<p class="meta">Mode: {escape(mode)}{" · " + escape(run_label) if run_label else ""} · '
        '<a href="https://github.com/gustavaom7/llm-eval-qa">source</a></p>',
        "<h2>Gates</h2>",
        '<p class="meta">A FAIL whose failures are all listed under Known findings is a reviewed, documented '
        "finding: CI accepts it and fails on anything new. Critical gates accept nothing.</p>",
    ]
    gate_rows = []
    for g in gates:
        status = "PASS" if g.passed else "FAIL"
        gate_rows.append(
            [
                escape(g.name),
                f'<span class="status {status}">{status}</span>',
                escape(_format(g, g.value)),
                escape(_format(g, g.threshold)),
            ]
        )
    parts.append(_table(["Gate", "Result", "Value", "Threshold"], gate_rows, {2, 3}))
    failing = [g for g in gates if not g.passed]
    if failing:
        parts += ["<h2>Failures</h2>", f"<pre>{escape(chr(10).join(g.message() for g in failing))}</pre>"]
    if attacks:
        table_lines = _red_team(attacks, gates)[4:]
        rows = [[escape(c.strip()) for c in line.strip("|").split("|")] for line in table_lines]
        parts += [
            "<h2>Red-team</h2>",
            _table(["Vulnerability", "Attacks", "Refused", "Answered", "Critical"], rows, {1, 2, 3, 4}),
        ]
    if known:
        rows = [[escape(g), escape(i), escape(w)] for g, items in known.items() for i, w in items.items()]
        parts += ["<h2>Known findings</h2>", _table(["Gate", "Item", "Why it is accepted"], rows)]
    timed = {m: v for m, v in latencies_ms.items() if v}
    if timed:
        rows = [
            [escape(m), str(len(v)), str(percentile(v, 50)), str(percentile(v, 95)), f"{sum(v) / 60_000:.1f}"]
            for m, v in timed.items()
        ]
        parts += [
            "<h2>Model latency</h2>",
            _table(["Model", "Calls", "p50 ms", "p95 ms", "Total min"], rows, {1, 2, 3, 4}),
        ]
    if budgets:
        rows = [[escape(k), escape(str(v))] for k, v in _flatten(budgets)]
        parts += ["<h2>Budgets in force</h2>", _table(["Budget", "Value"], rows)]
    parts.append("</main></body></html>")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
