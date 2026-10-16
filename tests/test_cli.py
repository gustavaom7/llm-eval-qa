from pathlib import Path

import pytest
import yaml

from support_bot.cli import main
from support_bot.llm import LLMUnavailable
from tests.fakes import FakeLLM

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "bot_model": "fake-model",
                "judge_model": "fake-judge",
                "ollama_host": "http://localhost:11434",
                "corpus_dir": str(ROOT / "corpus"),
                "cassette_dir": str(tmp_path / "cassettes"),
                "k": 3,
                "run_time_budget_minutes": 60,
            }
        )
    )
    return path


def test_ask_prints_answer_and_sources(config, capsys):
    code = main(
        ["ask", "How long is the free trial?", "--mode", "record", "--config", str(config)],
        llm=FakeLLM(default="The trial lasts 7 days."),
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "The trial lasts 7 days." in out
    assert any(line.startswith("Retrieved:") and "free-trial.md" in line for line in out.splitlines())
    assert "10 in / 5 out" in out
    assert "7 ms" in out


def test_empty_question_exits_2(config, capsys):
    assert main(["ask", "  ", "--config", str(config)], llm=FakeLLM()) == 2
    assert "Question is empty." in capsys.readouterr().err


def test_replay_without_cassette_exits_1(config, capsys):
    assert main(["ask", "How long is the free trial?", "--config", str(config)], llm=FakeLLM()) == 1
    assert "run the Record workflow" in capsys.readouterr().err


class DownLLM(FakeLLM):
    def complete(self, system, user):
        raise LLMUnavailable(
            "Ollama is not reachable at http://localhost:11434. Start it with `ollama serve`."
        )


def test_ollama_unavailable_exits_1(config, capsys):
    assert (
        main(["ask", "How long is the free trial?", "--mode", "live", "--config", str(config)], llm=DownLLM())
        == 1
    )
    assert "ollama serve" in capsys.readouterr().err


def test_replay_after_record_answers_without_model(config, capsys):
    main(
        ["ask", "How do I cancel?", "--mode", "record", "--config", str(config)],
        llm=FakeLLM(default="Cancel."),
    )
    untouched = FakeLLM(default="other")
    assert main(["ask", "How do I cancel?", "--config", str(config)], llm=untouched) == 0
    assert "Cancel." in capsys.readouterr().out
    assert untouched.calls == []


def test_corrupt_cassette_exits_1_not_empty_question(config, capsys, tmp_path):
    main(["ask", "How do I cancel?", "--mode", "record", "--config", str(config)], llm=FakeLLM())
    for cassette in (tmp_path / "cassettes").glob("*.json"):
        cassette.write_text("{truncated")
    assert main(["ask", "How do I cancel?", "--config", str(config)], llm=FakeLLM()) == 1
    err = capsys.readouterr().err
    assert "Question is empty" not in err
    assert "run the Record workflow" in err


@pytest.mark.parametrize("k", ["0", "-1"])
def test_k_below_one_is_rejected(config, capsys, k):
    with pytest.raises(SystemExit) as exc:
        main(["ask", "How do I cancel?", "--k", k, "--config", str(config)], llm=FakeLLM())
    assert exc.value.code == 2


def test_retrieved_line_is_not_labelled_sources(config, capsys):
    main(
        ["ask", "How do I cancel?", "--mode", "record", "--config", str(config)],
        llm=FakeLLM(default="Cancel in Account.\nSources: cancellation.md"),
    )
    out = capsys.readouterr().out
    assert sum(line.startswith("Sources:") for line in out.splitlines()) == 1
    assert any(line.startswith("Retrieved:") for line in out.splitlines())
