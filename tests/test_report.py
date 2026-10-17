from evals.gates import GateResult
from evals.report import write_summary


def gates():
    return [
        GateResult("Required facts", 0.9, 0.85, True, "9 of 10", []),
        GateResult("Input tokens per answer", 2600, 2500, False, "largest", ["a"], "tokens"),
    ]


def test_summary_lists_each_gate(tmp_path):
    path = tmp_path / "reports" / "summary.md"
    write_summary(path, gates(), {}, "replay")
    text = path.read_text()
    assert "| Gate | Result | Value | Threshold |" in text
    assert "| Required facts | PASS | 90% | 85% |" in text
    assert "| Input tokens per answer | FAIL | 2600 | 2500 |" in text
    assert "replay" in text
    assert "| Model |" not in text


def test_summary_reports_p95_latency(tmp_path):
    path = tmp_path / "summary.md"
    write_summary(path, gates(), {"qwen2.5:3b (bot)": [100 * n for n in range(1, 11)]}, "record")
    assert "| qwen2.5:3b (bot) | 10 | 500 | 1000 | 0.1 |" in path.read_text()


def test_summary_prints_budgets(tmp_path):
    path = tmp_path / "s.md"
    write_summary(
        path, gates(), {}, "replay", budgets={"citation_rate": 0.95, "live_only": {"p95_latency_ms": 20000}}
    )
    text = path.read_text()
    assert "## Budgets in force" in text
    assert "| citation_rate | 0.95 |" in text and "| live_only.p95_latency_ms | 20000 |" in text


def test_summary_lists_known_findings(tmp_path):
    path = tmp_path / "s.md"
    write_summary(path, gates(), {}, "replay", known={"Required facts": {"age-17": "retrieval miss"}})
    assert "| Required facts | age-17 | retrieval miss |" in path.read_text()


def test_summary_has_red_team_table(tmp_path):
    path = tmp_path / "s.md"
    rows = [("a", "pii_leakage", "plain", True), ("b", "pii_leakage", "leetspeak", False)]
    critical = GateResult(
        "Critical failures (red-team)", 1, 0, False, "d", ["b: personal data 'x@y.z'"], "count"
    )
    write_summary(path, [critical], {}, "replay", attacks=rows)
    text = path.read_text()
    assert "## Red-team" in text
    assert "| pii_leakage | 2 | 1 | 1 | 1 |" in text


def test_red_team_table_reads_the_red_team_gate_not_the_golden_one(tmp_path):
    from evals.critical import RED_TEAM_GATE

    path = tmp_path / "s.md"
    golden = GateResult("Critical failures", 0, 0, True, "d", [], "count")
    red = GateResult(RED_TEAM_GATE, 1, 0, False, "d", ["b: money promise 'x'"], "count")
    write_summary(path, [golden, red], {}, "record", attacks=[("b", "excessive_agency", "plain", False)])
    assert "| excessive_agency | 1 | 0 | 1 | 1 |" in path.read_text()
