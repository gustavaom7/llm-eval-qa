"""LLM-as-judge metrics (DeepEval) with a local judge model whose calls go through the recorder."""

from __future__ import annotations

from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, GEval
from deepeval.metrics.base_metric import BaseMetric
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, SingleTurnParams
from pydantic import BaseModel, ValidationError

from evals.dataset import GoldenItem
from evals.runner import MissingRecordings
from support_bot.bot import Answer
from support_bot.llm import LLMUnavailable
from support_bot.recorder import CassetteMissing, Recorder, RunTimeExceeded

POLICY_STEPS = [
    "Check the answer states every fact in the expected output.",
    "Penalize any claim that contradicts the expected output.",
    "Do not penalize extra correct detail or the Sources line.",
]

# Problems with the run itself, not with one judged answer: they stop the suite instead of scoring 0.
RUN_ERRORS = (RunTimeExceeded, LLMUnavailable)


class RecordedJudge(DeepEvalBaseLLM):
    def __init__(self, recorder: Recorder):
        self.recorder = recorder
        super().__init__(recorder.model)

    def load_model(self) -> RecordedJudge:
        return self

    def get_model_name(self) -> str:
        return self.recorder.model

    def generate(self, prompt: str, schema: type[BaseModel] | None = None) -> BaseModel | str:
        text = self.recorder.complete("", prompt, schema.model_json_schema() if schema else None).text
        if schema is None:
            return text
        try:
            return schema.model_validate_json(text)
        except ValidationError:
            return text  # DeepEval then tries its own JSON repair, and raises if that fails too

    async def a_generate(self, prompt: str, schema: type[BaseModel] | None = None) -> BaseModel | str:
        return self.generate(prompt, schema)


def build_metrics(judge: RecordedJudge) -> dict[str, BaseMetric]:
    return {
        # eval_mode pinned: DeepEval reads DEEPEVAL_EVAL_MODE from the environment and .env files, and its
        # other modes call a decision model outside the recorder.
        "faithfulness": FaithfulnessMetric(
            model=judge, include_reason=False, async_mode=False, eval_mode="llm"
        ),
        "answer_relevancy": AnswerRelevancyMetric(
            model=judge, include_reason=False, async_mode=False, eval_mode="llm"
        ),
        "policy_correctness": GEval(
            name="Policy correctness",
            evaluation_steps=POLICY_STEPS,
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.EXPECTED_OUTPUT,
            ],
            model=judge,
            async_mode=False,
        ),
    }


def judge_scores(
    items: list[GoldenItem], answers: dict[str, Answer], metrics: dict[str, BaseMetric]
) -> dict[str, dict[str, float | None]]:
    """Score metric -> item id -> score for the items marked judge: true; None when the judge's output
    could not be read."""
    scores: dict[str, dict[str, float | None]] = {name: {} for name in metrics}
    missing: list[str] = []
    for item in (i for i in items if i.judge):
        answer = answers[item.id]
        case = LLMTestCase(
            input=item.question,
            actual_output=answer.text,
            retrieval_context=answer.contexts,
            expected_output=item.reference_answer or "; ".join(item.canonical_facts),
        )
        for name, metric in metrics.items():
            try:
                metric.measure(case)
                scores[name][item.id] = metric.score
            except CassetteMissing:
                missing.append(item.id)
                break  # one missing verdict is enough to name the item
            except RUN_ERRORS:
                raise
            except Exception:  # noqa: BLE001 — any judge failure on one answer scores None, reported
                scores[name][item.id] = None
    if missing:
        raise MissingRecordings(missing, what="judge verdict")
    return scores
