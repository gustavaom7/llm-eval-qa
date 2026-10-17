"""The fixed red-team set (datasets/redteam.yaml), built from reviewed seeds."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

VULNERABILITIES = ("excessive_agency", "pii_leakage", "prompt_leakage", "robustness")


class RedTeamError(ValueError):
    """The red-team file breaks one of its rules."""


@dataclass(frozen=True)
class Attack:
    id: str
    seed: str
    vulnerability: str
    technique: str
    text: str

    @property
    def question(self) -> str:
        """The attack is what the customer sends; the bot runner reads it as the question."""
        return self.text


def load_attacks(path: Path) -> list[Attack]:
    attacks = [Attack(**row) for row in yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []]
    seen: set[str] = set()
    for a in attacks:
        if a.id in seen:
            raise RedTeamError(f"{a.id}: duplicate id")
        seen.add(a.id)
        if a.vulnerability not in VULNERABILITIES:
            raise RedTeamError(f"{a.id}: vulnerability must be one of {', '.join(VULNERABILITIES)}")
        if not a.text.strip():
            raise RedTeamError(f"{a.id}: empty text")
    return attacks
