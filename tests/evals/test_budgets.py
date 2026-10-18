"""Every threshold in budgets.yaml is read by some gate: a budget nothing enforces fails here."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = [*(ROOT / "tests" / "evals").glob("*.py")]


def flatten(budgets, prefix=""):
    for key, value in budgets.items():
        if isinstance(value, dict):
            yield from flatten(value, f"{prefix}{key}.")
        else:
            yield f"{prefix}{key}"


def test_every_budget_is_enforced(budgets):
    code = "\n".join(p.read_text() for p in SOURCES if p.name != "test_budgets.py")
    unread = [k for k in flatten(budgets) if not all(f'"{part}"' in code for part in k.split("."))]
    assert unread == [], f"budgets.yaml keys no gate reads: {unread}"
