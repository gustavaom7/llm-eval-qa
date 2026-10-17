import pytest

from evals.baseline import BaselineError, check_against_baseline, load_known
from evals.gates import GateResult

KNOWN = {"Required facts": {"age-17": "retrieval miss"}}


def result(passed, failures, name="Required facts"):
    return GateResult(name, 0.5, 0.85, passed, "detail", failures)


def test_passing_gate_is_fine():
    check_against_baseline(result(True, []), {})


def test_failure_on_a_known_finding_is_accepted():
    check_against_baseline(result(False, ["age-17: missing '18+'"]), KNOWN)


def test_new_failure_fails_with_the_item_named():
    with pytest.raises(AssertionError) as exc:
        check_against_baseline(result(False, ["age-17: missing '18+'", "refund: missing '14 days'"]), KNOWN)
    message = str(exc.value)
    assert "New failure" in message and "refund: missing '14 days'" in message
    assert "age-17" not in message.split("New failure")[1]


def test_known_finding_that_now_passes_must_be_removed():
    with pytest.raises(AssertionError, match="now passes.*age-17"):
        check_against_baseline(result(True, []), KNOWN)


def test_load_known_requires_a_reason(tmp_path):
    path = tmp_path / "known.yaml"
    path.write_text("Required facts:\n  age-17: ''\n")
    with pytest.raises(BaselineError, match="age-17"):
        load_known(path)


def test_load_known_reads_gates_and_reasons(tmp_path):
    path = tmp_path / "known.yaml"
    path.write_text("Required facts:\n  age-17: retrieval miss\n")
    assert load_known(path) == KNOWN


def test_baseline_refuses_known_critical_failures():
    known = {"Critical failures": {"a": "accepted"}}
    with pytest.raises(AssertionError, match="cannot be accepted as known findings"):
        check_against_baseline(result(False, ["a: money promise 'x'"], name="Critical failures"), known)
