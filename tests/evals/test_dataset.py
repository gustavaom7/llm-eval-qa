from collections import Counter
from pathlib import Path

import pytest
import yaml

from evals.dataset import DatasetError, check_against_corpus, load_golden

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "datasets" / "golden.yaml"
CORPUS = ROOT / "corpus"

VALID = {
    "id": "refund-window",
    "question": "How long do I have to ask for a refund?",
    "category": "fact",
    "expected_sources": ["refunds.md"],
    "must_include": ["14 days"],
    "must_not_include": [],
}
OUT_OF_SCOPE = {
    "id": "store",
    "question": "Where is the Lumen+ store?",
    "category": "out-of-scope",
    "expected_sources": [],
    "must_include": [],
    "must_not_include": [],
}


def write(tmp_path, *items):
    path = tmp_path / "golden.yaml"
    path.write_text(yaml.safe_dump(list(items)))
    return path


def test_golden_has_spec_distribution():
    items = load_golden(DATASET)
    counts = Counter(i.category for i in items)
    assert counts == {"fact": 16, "policy-edge": 12, "multi-doc": 6, "out-of-scope": 6}
    judged = Counter(i.category for i in items if i.judge)
    assert judged == {"fact": 4, "policy-edge": 5, "multi-doc": 3}


def test_multi_doc_items_have_two_sources():
    assert all(len(i.expected_sources) >= 2 for i in load_golden(DATASET) if i.category == "multi-doc")


def test_policy_edge_items_name_a_wrong_claim():
    assert all(i.must_not_include for i in load_golden(DATASET) if i.category == "policy-edge")


def test_valid_item_loads(tmp_path):
    [item] = load_golden(write(tmp_path, VALID))
    assert item.id == "refund-window" and item.judge is False


@pytest.mark.parametrize(
    "bad, message",
    [
        ({"category": "trivia"}, "category"),
        ({"extra": 1}, "unknown field"),
        ({"question": "  "}, "empty question"),
        ({"expected_sources": []}, "expected_sources"),
        ({"must_include": []}, "must_include"),
    ],
)
def test_invalid_items_are_rejected_with_their_id(tmp_path, bad, message):
    with pytest.raises(DatasetError, match=message) as exc:
        load_golden(write(tmp_path, {**VALID, **bad}))
    assert "refund-window" in str(exc.value)


def test_missing_field_is_rejected(tmp_path):
    item = {k: v for k, v in VALID.items() if k != "must_not_include"}
    with pytest.raises(DatasetError, match="missing field"):
        load_golden(write(tmp_path, item))


def test_duplicate_ids_are_rejected(tmp_path):
    with pytest.raises(DatasetError, match="duplicate id"):
        load_golden(write(tmp_path, VALID, VALID))


def test_out_of_scope_item_with_sources_is_rejected(tmp_path):
    with pytest.raises(DatasetError, match="out-of-scope"):
        load_golden(write(tmp_path, {**OUT_OF_SCOPE, "expected_sources": ["refunds.md"]}))


def test_judge_on_out_of_scope_is_rejected(tmp_path):
    with pytest.raises(DatasetError, match="judge"):
        load_golden(write(tmp_path, {**OUT_OF_SCOPE, "judge": True}))


def test_golden_passes_the_corpus_check():
    check_against_corpus(load_golden(DATASET), CORPUS)


def test_corpus_check_rejects_a_fact_missing_from_its_source(tmp_path):
    [item] = load_golden(write(tmp_path, {**VALID, "must_include": ["two weeks"]}))
    with pytest.raises(DatasetError, match="refund-window: 'two weeks' not found in refunds.md"):
        check_against_corpus([item], CORPUS)


def test_corpus_check_rejects_a_forbidden_phrase_the_corpus_states(tmp_path):
    [item] = load_golden(write(tmp_path, {**VALID, "must_not_include": ["5–10 business days"]}))
    with pytest.raises(
        DatasetError, match="refund-window: forbidden '5–10 business days' is stated in refunds.md"
    ):
        check_against_corpus([item], CORPUS)


def test_corpus_check_rejects_an_unknown_source(tmp_path):
    [item] = load_golden(write(tmp_path, {**VALID, "expected_sources": ["nope.md"]}))
    with pytest.raises(DatasetError, match="nope.md"):
        check_against_corpus([item], CORPUS)


def test_fact_with_alternative_phrasings_loads(tmp_path):
    [item] = load_golden(write(tmp_path, {**VALID, "must_include": [["14 days", "two weeks"]]}))
    assert item.facts == [["14 days", "two weeks"]]
    assert item.canonical_facts == ["14 days"]


@pytest.mark.parametrize("bad", [[[]], [["14 days", 3]], [3]])
def test_malformed_fact_is_rejected(tmp_path, bad):
    with pytest.raises(DatasetError, match="must_include"):
        load_golden(write(tmp_path, {**VALID, "must_include": bad}))


def test_corpus_check_needs_only_the_first_phrasing_in_the_source(tmp_path):
    [item] = load_golden(write(tmp_path, {**VALID, "must_include": [["14 days", "two weeks"]]}))
    check_against_corpus([item], CORPUS)


def test_judged_items_have_a_reference_answer():
    assert all(i.reference_answer for i in load_golden(DATASET) if i.judge)


def test_reference_answer_is_optional(tmp_path):
    [item] = load_golden(write(tmp_path, VALID))
    assert item.reference_answer == ""
