"""Deterministic gates on the bot's answers to the golden dataset (recorded answers in CI)."""

import pytest

from evals.baseline import check_against_baseline
from evals.critical import critical_gate
from evals.gates import (
    citation,
    cited_sources_exist,
    forbidden_claims,
    input_tokens,
    latency_p95,
    out_of_scope_refusal,
    required_facts,
)
from support_bot.bot import load_system_prompt

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


def test_no_critical_failures_in_golden_answers(golden, answers, check):
    check(critical_gate([(i.id, i.question, answers[i.id].text) for i in golden], load_system_prompt()))


def test_bot_latency_within_budget(mode, bot, answers, budgets, check):
    if mode != "live":
        pytest.skip("latency is measured on live runs only")
    check(latency_p95(bot.llm.latencies_ms, budgets["live_only"]["p95_latency_ms"]))


def test_cited_sources_exist(golden, answers, corpus_files, check):
    check(cited_sources_exist([(i.id, answers[i.id].text) for i in golden], corpus_files))
