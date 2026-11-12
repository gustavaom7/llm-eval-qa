"""Session fixtures for the evaluation suites: one bot run over the dataset, shared by every gate."""

import json
import os
import time
from pathlib import Path

import pytest

from evals.baseline import check_against_baseline, load_known
from evals.dataset import check_against_corpus, load_golden
from evals.report import write_html, write_summary
from evals.runner import build_bot, run_bot
from support_bot.cli import load_budgets, load_config
from support_bot.corpus import load_corpus
from support_bot.retriever import Retriever

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def mode(request):
    return request.config.getoption("--mode")


@pytest.fixture(scope="session")
def config():
    return load_config(ROOT / "config.yaml")


@pytest.fixture(scope="session")
def budgets(config):
    return load_budgets(config["budgets_file"])


@pytest.fixture(scope="session")
def time_budget_s(budgets, mode):
    active = budgets["live_only"] if mode == "live" else budgets
    return active["run_time_budget_minutes"] * 60


@pytest.fixture(scope="session")
def golden(config):
    items = load_golden(ROOT / "datasets" / "golden.yaml")
    check_against_corpus(items, config["corpus_dir"])  # a dataset error stops the run before any model call
    return items


@pytest.fixture(scope="session")
def known():
    return load_known(ROOT / "datasets" / "known_findings.yaml")


@pytest.fixture(scope="session")
def started():
    return time.monotonic()


@pytest.fixture(scope="session")
def retriever(config):
    return Retriever(load_corpus(config["corpus_dir"]))


@pytest.fixture(scope="session")
def recorders():
    """Every recorder of the run, by label, so the summary can report model latencies."""
    return {}


@pytest.fixture(scope="session")
def attack_log():
    """(id, vulnerability, technique, refused) rows the red-team suite records for the report."""
    return []


@pytest.fixture(scope="session")
def gate_log(recorders, mode, budgets, known, attack_log):
    results = []
    yield results
    latencies = {label: recorder.latencies_ms for label, recorder in recorders.items()}
    metadata_path = os.environ.get("OLLAMA_REPORT_METADATA")
    model_metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8")) if metadata_path else None
    extras = {"budgets": budgets, "known": known, "attacks": attack_log, "model_metadata": model_metadata}
    write_summary(ROOT / "reports" / "summary.md", results, latencies, mode, **extras)
    run = os.environ.get("GITHUB_RUN_NUMBER")
    label = f"CI run {run}, commit {os.environ.get('GITHUB_SHA', '')[:7]}" if run else "local run"
    write_html(ROOT / "reports" / "index.html", results, latencies, mode, run_label=label, **extras)


@pytest.fixture
def check(gate_log, known, mode):
    def check_gate(result):
        gate_log.append(result)
        check_against_baseline(result, known, live=mode == "live")

    return check_gate


@pytest.fixture(scope="session")
def bot(config, mode, started, recorders, time_budget_s):
    bot = build_bot(config, mode, started, time_budget_s=time_budget_s)
    recorders[f"{config['bot_model']} (bot)"] = bot.llm
    return bot


@pytest.fixture(scope="session")
def answers(bot, golden):
    return run_bot(bot, golden)


@pytest.fixture(scope="session")
def judge_scores_by_metric(config, mode, started, recorders, golden, answers, time_budget_s):
    from evals.judge import RecordedJudge, build_metrics, judge_scores
    from support_bot.llm import OllamaLLM
    from support_bot.recorder import Recorder

    llm = OllamaLLM(
        config["judge_model"],
        host=config["ollama_host"],
        options=config["judge_options"],
        timeout=config["request_timeout_s"],
    )
    recorder = Recorder(
        llm,
        config["cassette_dir"],
        mode=mode,
        time_budget_s=time_budget_s,
        started=started,
    )
    recorders[f"{config['judge_model']} (judge)"] = recorder
    return judge_scores(golden, answers, build_metrics(RecordedJudge(recorder)))


@pytest.fixture(scope="session")
def attack_pairs(golden):
    from evals.redteam import load_attacks

    pairs = load_attacks(ROOT / "datasets" / "redteam_pairs.yaml")
    controls = {item.id: item for item in golden if item.in_scope and item.facts}
    return [(attack, controls[attack.seed]) for attack in pairs]


@pytest.fixture(scope="session")
def attacks(attack_pairs):
    from evals.redteam import load_attacks

    return load_attacks(ROOT / "datasets" / "redteam.yaml") + [attack for attack, _ in attack_pairs]


@pytest.fixture(scope="session")
def attack_answers(bot, attacks):
    return run_bot(bot, attacks)


@pytest.fixture(scope="session")
def corpus_files(config):
    return {p.name for p in config["corpus_dir"].glob("*.md")}
