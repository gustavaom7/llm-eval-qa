import json

import pytest
from deepeval.metrics.faithfulness.schema import Truths

from evals.dataset import GoldenItem
from evals.judge import RecordedJudge, build_metrics, judge_scores
from evals.runner import MissingRecordings
from support_bot.bot import Answer
from support_bot.recorder import Recorder
from tests.fakes import FakeLLM

# What a well-behaved judge returns, by the title of the JSON schema DeepEval asks for.
GOOD = {
    "Truths": {"truths": ["Refunds are possible within 14 days."]},
    "Claims": {"claims": ["Refunds are possible within 14 days."]},
    "Statements": {"statements": ["Refunds are possible within 14 days."]},
    "Verdicts": {"verdicts": [{"verdict": "yes"}]},
    "ReasonScore": {"reason": "States the 14-day window.", "score": 10},
}


def good_judge(system, user, schema):
    return json.dumps(GOOD[schema["title"]])


def recorded(tmp_path, llm, mode="record"):
    return RecordedJudge(Recorder(llm, tmp_path, mode=mode))


ITEMS = [
    GoldenItem("judged", "Can I get a refund?", "fact", ["refunds.md"], ["14 days"], [], judge=True),
    GoldenItem("skipped", "How do I cancel?", "fact", ["cancellation.md"], ["Account"], []),
]
ANSWERS = {
    "judged": Answer("Within 14 days.\nSources: refunds.md", ["refunds.md"], 10, 5, 7, ["Refunds: 14 days."]),
    "skipped": Answer("In Account.", ["cancellation.md"], 10, 5, 7, ["Cancel in Account."]),
}


def test_generate_sends_schema_and_returns_model(tmp_path):
    llm = FakeLLM(default='{"truths": ["a"]}')
    assert recorded(tmp_path, llm).generate("prompt", schema=Truths) == Truths(truths=["a"])
    assert llm.calls == [("", "prompt", Truths.model_json_schema())]


def test_generate_returns_text_when_output_does_not_fit_schema(tmp_path):
    assert recorded(tmp_path, FakeLLM(default="not json")).generate("p", schema=Truths) == "not json"


def test_generate_without_schema_returns_text(tmp_path):
    assert recorded(tmp_path, FakeLLM(default="plain")).generate("p") == "plain"


def test_judge_name_is_the_wrapped_model(tmp_path):
    assert recorded(tmp_path, FakeLLM(model="qwen2.5:7b")).get_model_name() == "qwen2.5:7b"


def test_judge_calls_replay_from_cassettes(tmp_path):
    recorded(tmp_path, FakeLLM(default='{"truths": ["a"]}')).generate("p", schema=Truths)
    untouched = FakeLLM(default="must not be called")
    assert recorded(tmp_path, untouched, mode="replay").generate("p", schema=Truths) == Truths(truths=["a"])
    assert untouched.calls == []


def test_faithfulness_scores_through_recorded_judge(tmp_path):
    metrics = build_metrics(recorded(tmp_path, FakeLLM(responder=good_judge)))
    scores = judge_scores(ITEMS, ANSWERS, {"faithfulness": metrics["faithfulness"]})
    assert scores == {"faithfulness": {"judged": 1.0}}


def test_all_three_metrics_score(tmp_path):
    scores = judge_scores(ITEMS, ANSWERS, build_metrics(recorded(tmp_path, FakeLLM(responder=good_judge))))
    assert set(scores) == {"faithfulness", "answer_relevancy", "policy_correctness"}
    assert all(s["judged"] is not None for s in scores.values())


def test_unreadable_judge_output_scores_none(tmp_path):
    metrics = build_metrics(recorded(tmp_path, FakeLLM(default="not json")))
    assert judge_scores(ITEMS, ANSWERS, metrics)["faithfulness"] == {"judged": None}


def test_only_judge_items_are_scored(tmp_path):
    llm = FakeLLM(responder=good_judge)
    judge_scores(ITEMS, ANSWERS, build_metrics(recorded(tmp_path, llm)))
    assert not any("In Account." in user for _, user, _ in llm.calls)


def test_missing_judge_recordings_are_listed_by_item(tmp_path):
    second = GoldenItem("judged-2", "Refund?", "fact", ["refunds.md"], ["14 days"], [], judge=True)
    answers = {**ANSWERS, "judged-2": ANSWERS["judged"]}
    metrics = build_metrics(recorded(tmp_path, FakeLLM(), mode="replay"))
    with pytest.raises(MissingRecordings) as exc:
        judge_scores([*ITEMS, second], answers, metrics)
    message = str(exc.value)
    assert "judged, judged-2" in message and "Run the Record workflow" in message
    assert "judge" in message


def test_metrics_ignore_a_configured_eval_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPEVAL_EVAL_MODE", "hybrid")
    metrics = build_metrics(recorded(tmp_path, FakeLLM(responder=good_judge)))
    assert metrics["faithfulness"].eval_mode.value == "llm"
    assert metrics["answer_relevancy"].eval_mode.value == "llm"


def test_policy_correctness_compares_with_the_reference_answer(tmp_path):
    item = GoldenItem(
        "judged", "Can I get a refund?", "fact", ["refunds.md"], ["14 days"], [], judge=True,
        reference_answer="Yes, within 14 days of your first payment.",
    )
    llm = FakeLLM(responder=good_judge)
    judge_scores([item], ANSWERS, {"p": build_metrics(recorded(tmp_path, llm))["policy_correctness"]})
    assert any("Yes, within 14 days of your first payment." in user for _, user, _ in llm.calls)
