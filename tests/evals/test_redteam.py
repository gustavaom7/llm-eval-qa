"""Red-team: the fixed attack set (datasets/redteam.yaml) must produce zero critical failures."""

import pytest

from evals.baseline import check_against_baseline
from evals.critical import RED_TEAM_GATE, critical_gate
from evals.gates import cited_sources_exist
from evals.redteam import attack_context
from support_bot.bot import REFUSAL, load_system_prompt

pytestmark = pytest.mark.redteam


def test_no_critical_failures_under_attack(attacks, attack_answers, gate_log, known, attack_log):
    attack_log.extend(
        (a.id, a.vulnerability, a.technique, REFUSAL in attack_answers[a.id].text) for a in attacks
    )
    cases = [(a.id, attack_context(a, attacks), attack_answers[a.id].text) for a in attacks]
    result = critical_gate(cases, load_system_prompt(), name=RED_TEAM_GATE)
    gate_log.append(result)
    check_against_baseline(result, known)


def test_attack_answers_cite_only_real_files(attacks, attack_answers, corpus_files, gate_log, known):
    cases = [(a.id, attack_answers[a.id].text) for a in attacks]
    result = cited_sources_exist(cases, corpus_files, name="Cited sources exist (red-team)")
    gate_log.append(result)
    check_against_baseline(result, known)
