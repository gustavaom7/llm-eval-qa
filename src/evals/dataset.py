"""The golden dataset: questions with the sources and facts a correct answer needs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

CATEGORIES = ("fact", "policy-edge", "multi-doc", "out-of-scope")
REQUIRED = ("id", "question", "category", "expected_sources", "must_include", "must_not_include")
OPTIONAL = ("judge",)


class DatasetError(ValueError):
    """The dataset file breaks one of its rules."""


@dataclass(frozen=True)
class GoldenItem:
    id: str
    question: str
    category: str
    expected_sources: list[str]
    must_include: list[str | list[str]]  # a phrase, or a list of accepted phrasings
    must_not_include: list[str]
    judge: bool = False

    @property
    def in_scope(self) -> bool:
        return self.category != "out-of-scope"

    @property
    def facts(self) -> list[list[str]]:
        """Each required fact as its accepted phrasings; the first is the one written in the source."""
        return [[f] if isinstance(f, str) else list(f) for f in self.must_include]

    @property
    def canonical_facts(self) -> list[str]:
        return [phrasings[0] for phrasings in self.facts]


def _check(raw: dict, index: int) -> GoldenItem:
    label = raw.get("id", f"item {index + 1}")
    unknown = sorted(set(raw) - set(REQUIRED) - set(OPTIONAL))
    if unknown:
        raise DatasetError(f"{label}: unknown field {', '.join(unknown)}")
    missing = [f for f in REQUIRED if f not in raw]
    if missing:
        raise DatasetError(f"{label}: missing field {', '.join(missing)}")
    item = GoldenItem(**raw)
    if not str(item.question).strip():
        raise DatasetError(f"{label}: empty question")
    if item.category not in CATEGORIES:
        raise DatasetError(f"{label}: category must be one of {', '.join(CATEGORIES)}, got {item.category!r}")
    for fact in item.must_include:
        phrasings = [fact] if isinstance(fact, str) else fact
        if not isinstance(phrasings, list) or not phrasings or not all(isinstance(p, str) for p in phrasings):
            raise DatasetError(f"{label}: each must_include entry is a phrase or a list of accepted phrases")
    if item.in_scope:
        if not item.expected_sources:
            raise DatasetError(f"{label}: an in-scope item needs expected_sources")
        if not item.must_include:
            raise DatasetError(f"{label}: an in-scope item needs must_include")
    else:
        if item.expected_sources or item.must_include:
            raise DatasetError(f"{label}: an out-of-scope item has no expected_sources or must_include")
        if item.judge:
            raise DatasetError(f"{label}: out-of-scope items are not judged (judge: true)")
    return item


def load_golden(path: Path) -> list[GoldenItem]:
    raw_items = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []
    items = [_check(raw, index) for index, raw in enumerate(raw_items)]
    seen: set[str] = set()
    for item in items:
        if item.id in seen:
            raise DatasetError(f"{item.id}: duplicate id")
        seen.add(item.id)
    return items


def check_against_corpus(items: list[GoldenItem], corpus_dir: Path) -> None:
    """Fail before any model runs when the dataset disagrees with the corpus: an unknown source, a required
    fact its sources do not state word for word, or a forbidden claim the corpus itself states."""
    docs = {p.name: p.read_text(encoding="utf-8").lower() for p in Path(corpus_dir).glob("*.md")}
    for item in items:
        unknown = [s for s in item.expected_sources if s not in docs]
        if unknown:
            raise DatasetError(f"{item.id}: unknown source {', '.join(unknown)}")
        for fact in item.canonical_facts:
            if not any(fact.lower() in docs[s] for s in item.expected_sources):
                raise DatasetError(f"{item.id}: '{fact}' not found in {', '.join(item.expected_sources)}")
        for claim in item.must_not_include:
            stated = [name for name, text in sorted(docs.items()) if claim.lower() in text]
            if stated:
                raise DatasetError(f"{item.id}: forbidden '{claim}' is stated in {', '.join(stated)}")
