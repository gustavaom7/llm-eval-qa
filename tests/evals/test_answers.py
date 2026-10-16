"""Deterministic gates on the bot's answers to the golden dataset (recorded answers in CI)."""

import pytest

from evals.gates import citation, forbidden_claims, input_tokens, out_of_scope_refusal, required_facts

pytestmark = pytest.mark.quality


def check(result, gate_log):
    gate_log.append(result)
    assert result.passed, result.message()


def test_required_facts(golden, answers, budgets, gate_log):
    check(required_facts(golden, answers, budgets["required_facts_rate"]), gate_log)


def test_no_forbidden_claims(golden, answers, gate_log):
    check(forbidden_claims(golden, answers), gate_log)


def test_out_of_scope_is_refused(golden, answers, gate_log):
    check(out_of_scope_refusal(golden, answers), gate_log)


def test_answers_cite_sources(golden, answers, budgets, gate_log):
    check(citation(golden, answers, budgets["citation_rate"]), gate_log)


def test_input_tokens_within_budget(answers, budgets, gate_log):
    check(input_tokens(answers, budgets["max_input_tokens_per_answer"]), gate_log)
