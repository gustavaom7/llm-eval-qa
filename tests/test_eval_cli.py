import json
import shutil
from pathlib import Path

import yaml

from evals import cli
from evals.runner import build_bot
from tests.fakes import FakeLLM

ROOT = Path(__file__).resolve().parents[1]


def test_missing_and_record_use_the_same_cassette_keys(tmp_path, monkeypatch, capsys):
    shutil.copytree(ROOT / "datasets", tmp_path / "datasets")
    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    config.update(corpus_dir=str(ROOT / "corpus"), budgets_file=str(ROOT / "budgets.yaml"))
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config))
    model = FakeLLM(model=config["bot_model"], options=config["bot_options"])
    monkeypatch.setattr(cli, "build_bot", lambda *args, **kwargs: build_bot(*args, **kwargs, llm=model))
    common = ["--config", str(config_path), "--ids", "phone-support"]

    assert cli.main(["missing", *common]) == 0
    assert json.loads(capsys.readouterr().out) == [{"id": "phone-support", "stage": "answer"}]
    assert model.calls == []

    output = tmp_path / "selected.json"
    assert cli.main(["record", *common, "--output", str(output)]) == 0
    assert len(model.calls) == 1
    assert set(json.loads(output.read_text())["cases"]) == {"phone-support"}
    capsys.readouterr()

    assert cli.main(["missing", *common]) == 0
    assert json.loads(capsys.readouterr().out) == []
    assert len(model.calls) == 1


def test_comparison_reports_changes_by_case(tmp_path, capsys):
    common = {"schema_version": 1, "mode": "live", "model_metadata": {}}
    case = {"question": "Price?", "sources": ["plans.md"], "answer": "Old", "scores": {}, "latency_ms": 10}
    before, after = tmp_path / "before.json", tmp_path / "after.json"
    before.write_text(json.dumps({**common, "cases": {"price": case, "removed": case}}))
    after.write_text(json.dumps({**common, "cases": {
        "price": {**case, "answer": "New", "scores": {"policy": 1.0}, "latency_ms": 20}, "added": case,
    }}))
    assert cli.main(["compare", str(before), str(after)]) == 0
    output = capsys.readouterr().out
    assert "added: added" in output
    assert "removed: absent from the second report" in output
    assert "answer: 'Old' -> 'New'" in output
    assert "scores: {} -> {'policy': 1.0}" in output
    assert "latency_ms: 10 -> 20" in output
