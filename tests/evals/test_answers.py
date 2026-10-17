"""Deterministic gates on the bot's answers to the golden dataset (recorded answers in CI)."""

import pytest

from evals.baseline import check_against_baseline
from evals.gates import citation, forbidden_claims, input_tokens, out_of_scope_refusal, required_facts

pytestmark = pytest.mark.quality


@pytest.fixture
def check(gate_log, known):
    def _check(result):
        gate_log.append(result)
        check_against_baseline(result, known)

    return _check


def test_required_facts(golden, answers, budgets, check):
    check(required_facts(golden, answers, budgets["required_facts_rate"]))


def test_no_forbidden_claims(golden, answers, check):
    check(forbidden_claims(golden, answers))


def test_out_of_scope_is_refused(golden, answers, check):
    check(out_of_scope_refusal(golden, answers))


def test_answers_cite_sources(golden, answers, budgets, check):
    check(citation(golden, answers, budgets["citation_rate"]))


def test_input_tokens_within_budget(answers, budgets, check):
    check(input_tokens(answers, budgets["max_input_tokens_per_answer"]))
