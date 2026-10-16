import pytest

from evals.dataset import GoldenItem
from evals.gates import (
    GateResult,
    citation,
    forbidden_claims,
    input_tokens,
    judge_mean,
    out_of_scope_refusal,
    required_facts,
    retrieval_recall,
)
from support_bot.bot import REFUSAL, Answer


def item(id, category="fact", sources=("refunds.md",), include=("14 days",), exclude=()):
    if category == "out-of-scope":
        sources, include = (), ()
    return GoldenItem(id, f"question {id}?", category, list(sources), list(include), list(exclude))


def answer(text, sources=("refunds.md",), tokens=100):
    return Answer(text, list(sources), tokens, 10, 5)


def test_message_is_readable():
    r = GateResult(
        "Required facts",
        0.5,
        0.85,
        False,
        "1 of 2 answers state every required fact",
        ["refund-window-edge: missing '14 days'"],
    )
    assert r.message() == (
        "Required facts: FAIL — 1 of 2 answers state every required fact; gate 85%\n"
        "  - refund-window-edge: missing '14 days'"
    )


def test_message_truncates_after_ten_failures():
    r = GateResult("X", 0.0, 1.0, False, "none", [f"f{n}" for n in range(13)])
    lines = r.message().splitlines()
    assert lines[1:11] == [f"  - f{n}" for n in range(10)]
    assert lines[11] == "  - … and 3 more"


def test_retrieval_recall_averages_over_in_scope_items():
    items = [
        item("a"),
        item("b", "multi-doc", sources=("refunds.md", "billing.md")),
        item("c", "out-of-scope"),
    ]
    r = retrieval_recall(items, {"a": ["refunds.md"], "b": ["refunds.md", "pause.md"], "c": []}, 0.9)
    assert r.value == pytest.approx(0.75)
    assert not r.passed
    assert r.failures == ["b: billing.md not in the top 3 (got refunds.md, pause.md)"]


def test_required_facts_ignores_case():
    r = required_facts([item("a")], {"a": answer("Within 14 DAYS of payment.")}, 0.85)
    assert (r.value, r.passed, r.failures) == (1.0, True, [])


def test_required_facts_lists_missing_facts():
    items = [item("a", include=("14 days", "2 hours")), item("b")]
    r = required_facts(items, {"a": answer("14 days"), "b": answer("14 days")}, 0.85)
    assert r.value == 0.5 and not r.passed
    assert r.failures == ["a: missing '2 hours'"]
    assert r.detail == "1 of 2 answers state every required fact"


def test_forbidden_claims_must_never_appear():
    items = [item("a", exclude=("full refund at any time",)), item("b", exclude=("phone",))]
    r = forbidden_claims(items, {"a": answer("A FULL REFUND AT ANY TIME."), "b": answer("chat only")})
    assert not r.passed and r.threshold == 1.0
    assert r.failures == ["a: says 'full refund at any time'"]


def test_refusal_gate_fails_when_out_of_scope_item_is_answered():
    items = [item("x", "out-of-scope"), item("y", "out-of-scope"), item("a")]
    answers = {"x": answer(REFUSAL, ()), "y": answer("Our CEO is Jane."), "a": answer("14 days")}
    r = out_of_scope_refusal(items, answers)
    assert r.value == 0.5 and not r.passed
    assert r.failures == ["y: answered instead of refusing: 'Our CEO is Jane.'"]


def test_citation_needs_a_retrieved_source_in_the_answer():
    items = [item("a"), item("b"), item("x", "out-of-scope")]
    answers = {
        "a": answer("14 days.\nSources: refunds.md"),
        "b": answer("14 days.", sources=("refunds.md",)),
        "x": answer(REFUSAL, ()),
    }
    r = citation(items, answers, 0.95)
    assert r.value == 0.5 and not r.passed
    assert r.failures == ["b: names none of refunds.md"]


def test_input_tokens_gate_reports_largest():
    r = input_tokens({"a": answer("x", tokens=900), "b": answer("x", tokens=2600)}, 2500)
    assert (r.value, r.passed) == (2600, False)
    assert r.failures == ["b: 2600 input tokens"]
    assert "gate 2500 tokens" in r.message()


def test_judge_mean_counts_unreadable_as_zero_and_lists_it():
    r = judge_mean("Faithfulness", {"a": 1.0, "b": None}, 0.7)
    assert r.value == 0.5 and not r.passed
    assert "b: judge output unreadable" in r.failures


def test_judge_mean_passes_above_threshold_and_lists_low_scores():
    r = judge_mean("Faithfulness", {"a": 1.0, "b": 0.6}, 0.7)
    assert r.passed and r.value == pytest.approx(0.8)
    assert r.failures == ["b: 0.60"]


def test_required_facts_treat_dash_variants_alike():
    r = required_facts(
        [item("a", include=("5–10 business days",))], {"a": answer("5-10 business days")}, 0.85
    )
    assert r.passed


def test_required_facts_treat_hyphenated_and_spaced_forms_alike():
    r = required_facts([item("a", include=("7-day",))], {"a": answer("The free trial is 7 days long.")}, 0.85)
    assert r.passed
