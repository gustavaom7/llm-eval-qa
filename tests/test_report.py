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
