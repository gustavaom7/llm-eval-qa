import re
from collections import Counter
from pathlib import Path

import pytest
import yaml

from evals.critical import _luhn
from evals.redteam import RedTeamError, load_attacks

ROOT = Path(__file__).resolve().parents[1]
SEEDS = ROOT / "datasets" / "redteam_seeds.yaml"
REDTEAM = ROOT / "datasets" / "redteam.yaml"


def test_redteam_file_is_up_to_date(tmp_path):
    pytest.importorskip("deepteam")
    from scripts.build_redteam import build

    build(SEEDS, tmp_path / "out.yaml")
    assert (tmp_path / "out.yaml").read_text() == REDTEAM.read_text(), "run: python scripts/build_redteam.py"


def test_committed_set_has_44_attacks_across_four_vulnerabilities():
    attacks = load_attacks(REDTEAM)
    assert len(attacks) == 44
    assert Counter(a.vulnerability for a in attacks) == {
        "excessive_agency": 11,
        "pii_leakage": 11,
        "prompt_leakage": 11,
        "robustness": 11,
    }
    assert sum(a.technique in ("base64", "rot13") for a in attacks) == 4


def test_variant_ids_name_their_seed_and_technique():
    for a in load_attacks(REDTEAM):
        assert a.id == a.seed if a.technique == "plain" else a.id == f"{a.seed}--{a.technique}"


def test_attack_exposes_its_text_as_the_question():
    a = load_attacks(REDTEAM)[0]
    assert a.question == a.text


def test_duplicate_attack_ids_are_rejected(tmp_path):
    row = {"id": "x", "seed": "x", "vulnerability": "robustness", "technique": "plain", "text": "hi"}
    path = tmp_path / "r.yaml"
    path.write_text(yaml.safe_dump([row, row]))
    with pytest.raises(RedTeamError, match="duplicate id"):
        load_attacks(path)


def test_unknown_vulnerability_is_rejected(tmp_path):
    row = {"id": "x", "seed": "x", "vulnerability": "toxicity", "technique": "plain", "text": "hi"}
    path = tmp_path / "r.yaml"
    path.write_text(yaml.safe_dump([row]))
    with pytest.raises(RedTeamError, match="vulnerability"):
        load_attacks(path)


def test_seeds_use_only_reserved_example_data():
    text = SEEDS.read_text()
    assert all(e.endswith("@example.com") for e in re.findall(r"[\w.+-]+@[\w.-]+", text))
    numbers = [re.sub(r"\D", "", n) for n in re.findall(r"\d(?:[ -]?\d){12,18}", text)]
    assert not [n for n in numbers if _luhn(n)]
