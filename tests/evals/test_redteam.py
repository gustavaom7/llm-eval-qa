"""Red-team: the fixed attack set (datasets/redteam.yaml) must produce zero critical failures."""

import pytest

from evals.baseline import check_against_baseline
from evals.critical import RED_TEAM_GATE, critical_gate
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
