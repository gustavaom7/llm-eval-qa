"""Inspect, record, compare and calibrate evaluations from the command line."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from evals.dataset import GoldenItem, check_against_corpus, load_golden
from evals.redteam import load_attacks
from evals.runner import MissingRecordings, build_bot, run_bot
from evals.snapshots import compare_snapshots, model_metadata, write_snapshot
from support_bot.cli import load_budgets, load_config
from support_bot.llm import LLMUnavailable
from support_bot.recorder import RunTimeExceeded


def _cases(args, config, golden, budgets, judge, started):
    from evals.judge import build_metrics, judge_scores

    mode = "replay" if args.command == "missing" else "record"
    directory = args.config.parent / "datasets"
    items = golden + load_attacks(directory / "redteam.yaml") + load_attacks(directory / "redteam_pairs.yaml")
    by_id = {item.id: item for item in items}
    if len(by_id) != len(items):
        raise ValueError("Case IDs must be unique across datasets.")
    if args.ids or mode == "record":
        ids = dict.fromkeys(case_id.strip() for case_id in args.ids.split(","))
        unknown = ids.keys() - by_id.keys()
        if unknown:
            raise ValueError(f"Unknown case IDs: {', '.join(sorted(unknown))}")
        items = [by_id[case_id] for case_id in ids]
    bot = build_bot(config, mode, started, time_budget_s=budgets["run_time_budget_minutes"] * 60)
    metrics = build_metrics(judge)
    answers, questions, scores = {}, {}, {name: {} for name in metrics}
    missing = []
    for item in items:
        stage = "answer"
        try:
            answer = run_bot(bot, [item])
            stage = "judge"
            verdicts = judge_scores([item], answer, metrics) if isinstance(item, GoldenItem) else {}
        except MissingRecordings as exc:
            if mode == "record":
                raise
            missing.extend({"id": case_id, "stage": stage} for case_id in exc.ids)
            continue
        answers.update(answer)
        questions[item.id] = item.question
        for name, values in verdicts.items():
            scores[name].update(values)
    if mode == "replay":
        print(json.dumps(missing, indent=2))
    else:
        write_snapshot(args.output, mode, answers, questions, scores, model_metadata=model_metadata())
        print(f"Recorded or reused {len(answers)} cases. Report: {args.output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="llm-eval")
    commands = parser.add_subparsers(dest="command", required=True)
    missing = commands.add_parser("missing", help="list case IDs with missing or unreadable cassettes")
    missing.add_argument("--ids", default="", help="optional comma-separated case IDs")
    record = commands.add_parser("record", help="record missing bot and judge calls for selected cases")
    record.add_argument("--ids", required=True, help="comma-separated case IDs")
    record.add_argument("--output", type=Path, default=Path("reports/cases.json"))
    calibration = commands.add_parser("calibrate", help="compare policy rubrics against reviewed examples")
    calibration.add_argument("--output", type=Path, default=Path("reports/calibration.json"))
    diff = commands.add_parser("compare", help="compare two cases.json reports")
    diff.add_argument("before", type=Path)
    diff.add_argument("after", type=Path)
    for command in (missing, record, calibration):
        command.add_argument("--config", type=Path, default=Path("config.yaml"))
    args = parser.parse_args(argv)

    try:
        if args.command == "compare":
            print(compare_snapshots(args.before, args.after))
            return 0
        os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
        from evals.judge import build_judge

        config = load_config(args.config)
        budgets = load_budgets(config["budgets_file"])
        directory = args.config.parent / "datasets"
        golden = load_golden(directory / "golden.yaml")
        check_against_corpus(golden, config["corpus_dir"])
        mode = {"missing": "replay", "record": "record", "calibrate": "live"}[args.command]
        started = time.monotonic()
        judge = build_judge(config, mode, started, budgets["run_time_budget_minutes"] * 60)
        if args.command == "calibrate":
            from evals.calibration import calibrate

            report = calibrate(
                directory / "judge_calibration.yaml", golden, judge,
                budgets["judge_min_mean"]["policy_correctness"],
            )
            report["model_metadata"] = model_metadata()
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            for rubric, result in report["rubrics"].items():
                print(f"{rubric}: {result['agreed']}/{len(result['examples'])} matched the reviewed labels")
            return 0
        return _cases(args, config, golden, budgets, judge, started)
    except (OSError, ValueError, KeyError, MissingRecordings, LLMUnavailable, RunTimeExceeded) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
