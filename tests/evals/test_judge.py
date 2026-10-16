"""LLM-as-judge metrics: they fail only on a large drop (mean below budgets.yaml); the rest is reported."""

import pytest

from evals.gates import judge_mean

pytestmark = pytest.mark.quality


@pytest.mark.parametrize(
    "key, name",
    [
        ("faithfulness", "Judge: faithfulness"),
        ("answer_relevancy", "Judge: answer relevancy"),
        ("policy_correctness", "Judge: policy correctness"),
    ],
)
def test_judge_mean(key, name, judge_scores_by_metric, budgets, gate_log):
    result = judge_mean(name, judge_scores_by_metric[key], budgets["judge_min_mean"][key])
    gate_log.append(result)
    assert result.passed, result.message()
