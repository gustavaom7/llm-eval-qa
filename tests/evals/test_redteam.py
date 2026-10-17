"""Red-team: the fixed attack set (datasets/redteam.yaml) must produce zero critical failures."""

import pytest

from evals.baseline import check_against_baseline
from evals.critical import critical_gate
from support_bot.bot import load_system_prompt

pytestmark = pytest.mark.redteam


def test_no_critical_failures_under_attack(attacks, attack_answers, gate_log, known):
    cases = [(a.id, a.text, attack_answers[a.id].text) for a in attacks]
    result = critical_gate(cases, load_system_prompt())
    gate_log.append(result)
    check_against_baseline(result, known)
