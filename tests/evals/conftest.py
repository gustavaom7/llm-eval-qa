"""Session fixtures for the evaluation suites: one bot run over the dataset, shared by every gate."""

import time
from pathlib import Path

import pytest

from evals.baseline import load_known
from evals.dataset import check_against_corpus, load_golden
from evals.report import write_summary
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
    write_summary(
        ROOT / "reports" / "summary.md",
        results,
        latencies,
        mode,
        budgets=budgets,
        known=known,
        attacks=attack_log,
    )


@pytest.fixture(scope="session")
def bot(config, budgets, mode, started, recorders):
    bot = build_bot(config, mode, started, time_budget_s=budgets["run_time_budget_minutes"] * 60)
    recorders[f"{config['bot_model']} (bot)"] = bot.llm
    return bot


@pytest.fixture(scope="session")
def answers(bot, golden):
    return run_bot(bot, golden)


@pytest.fixture(scope="session")
def judge_scores_by_metric(config, budgets, mode, started, recorders, golden, answers):
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
        time_budget_s=budgets["run_time_budget_minutes"] * 60,
        started=started,
    )
    recorders[f"{config['judge_model']} (judge)"] = recorder
    return judge_scores(golden, answers, build_metrics(RecordedJudge(recorder)))


@pytest.fixture(scope="session")
def attacks():
    from evals.redteam import load_attacks

    return load_attacks(ROOT / "datasets" / "redteam.yaml")


@pytest.fixture(scope="session")
def attack_answers(bot, attacks):
    return run_bot(bot, attacks)


@pytest.fixture(scope="session")
def corpus_files(config):
    return {p.name for p in config["corpus_dir"].glob("*.md")}
