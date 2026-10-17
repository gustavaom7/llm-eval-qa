from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def load(name):
    return yaml.safe_load((WORKFLOWS / name).read_text())


def test_record_workflow_has_manual_and_monthly_triggers():
    triggers = load("record.yml")[True]  # YAML 1.1 reads the key `on` as True
    mode = triggers["workflow_dispatch"]["inputs"]["mode"]
    assert mode["options"] == ["record", "live"] and mode["default"] == "record"
    assert triggers["schedule"] == [{"cron": "17 6 1 * *"}]


def test_workflows_use_no_secrets():
    for name in ("ci.yml", "record.yml"):
        assert "secrets." not in (WORKFLOWS / name).read_text()


def test_record_workflow_never_pushes_to_main():
    text = (WORKFLOWS / "record.yml").read_text()
    pushes = [line.strip() for line in text.splitlines() if "git push" in line]
    assert pushes == ["git push origin HEAD"]
    assert "git switch -c cassettes/run-${{ github.run_id }}-${{ github.run_attempt }}" in text
    assert text.index("git switch -c cassettes/run-") < text.index("git push origin HEAD")


def test_push_step_tolerates_a_run_that_recorded_nothing():
    steps = load("record.yml")["jobs"]["evaluate"]["steps"]
    push = next(s for s in steps if s.get("name") == "Push cassettes")["run"]
    assert "[ -d cassettes ] || exit 0" in push
    assert "git add cassettes/*.json" in push


def test_record_workflow_saves_cassettes_before_failing_on_gates():
    steps = load("record.yml")["jobs"]["evaluate"]["steps"]
    names = [s.get("name") for s in steps]
    evals = next(s for s in steps if s.get("id") == "evals")
    assert evals["continue-on-error"] is True
    assert names.index("Push cassettes") < names.index("Fail if a gate failed")


def test_ci_runs_every_gate_on_recorded_answers():
    text = (WORKFLOWS / "ci.yml").read_text()
    assert "run: pytest -v\n" in text
    assert "not quality" not in text
