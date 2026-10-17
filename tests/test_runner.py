from pathlib import Path

import pytest

from evals.dataset import GoldenItem
from evals.runner import MissingRecordings, build_bot, run_bot
from tests.fakes import FakeLLM

ROOT = Path(__file__).resolve().parents[1]


def config(tmp_path):
    return {
        "bot_model": "fake-model",
        "ollama_host": "http://localhost:11434",
        "bot_options": {"temperature": 0},
        "request_timeout_s": 600,
        "corpus_dir": ROOT / "corpus",
        "cassette_dir": tmp_path / "cassettes",
        "k": 3,
    }


ITEMS = [
    GoldenItem("trial", "How long is the free trial?", "fact", ["free-trial.md"], ["7-day"], []),
    GoldenItem("refund", "Can I get a refund?", "fact", ["refunds.md"], ["14 days"], []),
    GoldenItem("cancel", "How do I cancel?", "fact", ["cancellation.md"], ["Account"], []),
]


def test_run_bot_answers_every_item(tmp_path):
    bot = build_bot(config(tmp_path), "record", started=None, llm=FakeLLM(default="answer"))
    answers = run_bot(bot, ITEMS)
    assert list(answers) == ["trial", "refund", "cancel"]
    assert all(a.text == "answer" for a in answers.values())


def test_missing_recordings_are_reported_together(tmp_path):
    bot = build_bot(config(tmp_path), "replay", started=None, llm=FakeLLM())
    with pytest.raises(MissingRecordings) as exc:
        run_bot(bot, ITEMS)
    message = str(exc.value)
    assert "3 items" in message and "Run the Record workflow" in message
    assert all(i.id in message for i in ITEMS)


def test_build_bot_uses_ollama_with_config_options(tmp_path, monkeypatch):
    seen = {}

    def fake_ollama(model, **kwargs):
        seen.update(kwargs, model=model)
        return FakeLLM()

    monkeypatch.setattr("evals.runner.OllamaLLM", fake_ollama)
    build_bot(config(tmp_path), "live", started=None)
    assert seen == {
        "model": "fake-model",
        "host": "http://localhost:11434",
        "options": {"temperature": 0},
        "timeout": 600,
    }


def test_run_bot_accepts_attacks(tmp_path):
    from evals.redteam import Attack

    attack = Attack("a", "a", "robustness", "plain", "Can I get a refund?")
    bot = build_bot(config(tmp_path), "record", started=None, llm=FakeLLM(default="No."))
    assert run_bot(bot, [attack])["a"].text == "No."
