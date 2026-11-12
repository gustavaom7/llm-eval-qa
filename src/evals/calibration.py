"""Compare policy rubrics against human-reviewed examples."""

from dataclasses import replace
from pathlib import Path

import yaml

from evals.dataset import GoldenItem
from evals.judge import POLICY_STEPS, RecordedJudge, judge_scores, policy_metric
from support_bot.bot import Answer

CANDIDATE_STEPS = [
    "Break the expected output into separate facts. Keep each condition, action, and deadline together.",
    "For each fact, mark it supported, omitted, or contradicted by the actual output.",
    "Different actions can have different deadlines. Compare deadlines only for the same action.",
    "Score a complete supported answer highly, penalize omissions, and penalize contradictions more.",
    "Ignore citations and correct additional details.",
]


def calibrate(
    path: Path, golden: list[GoldenItem], judge: RecordedJudge, threshold: float
) -> dict:
    controls = {item.id: item for item in golden}
    rows = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases = []
    answers = {}
    labels = {"correct", "incomplete", "contradictory"}
    for row in rows:
        case_id = row["id"]
        if case_id in answers or row["label"] not in labels:
            raise ValueError(f"Invalid calibration example: {case_id}")
        cases.append(replace(controls[row["golden_id"]], id=case_id, judge=True))
        answers[case_id] = Answer(row["answer"], [], 0, 0, 0)
    if not cases:
        raise ValueError("Calibration requires at least one reviewed example.")
    metrics = {
        "current": policy_metric(judge, POLICY_STEPS),
        "candidate": policy_metric(judge, CANDIDATE_STEPS),
    }
    scores = judge_scores(cases, answers, metrics)
    result = {"threshold": threshold, "rubrics": {}}
    for rubric, values in scores.items():
        examples = []
        for row in rows:
            score = values[row["id"]]
            expected_pass = row["label"] == "correct"
            verdict = None if score is None else score >= threshold
            agrees = verdict is not None and verdict == expected_pass
            examples.append({**row, "score": score, "agrees": agrees})
        result["rubrics"][rubric] = {"agreed": sum(row["agrees"] for row in examples), "examples": examples}
    return result
