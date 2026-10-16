"""Load the policy documents and split them into heading-based chunks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Chunk:
    id: str
    doc: str
    heading: str
    text: str


def _split_sections(markdown: str) -> tuple[str, list[tuple[str, str]]]:
    """Return the H1 title and (heading, body) pairs; text before the first H2 belongs to the title."""
    title = ""
    sections: list[tuple[str, list[str]]] = []
    for line in markdown.splitlines():
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            sections.append((title, []))
        elif line.startswith("## "):
            sections.append((line[3:].strip(), []))
        elif sections:
            sections[-1][1].append(line)
    return title, [(heading, "\n".join(body).strip()) for heading, body in sections]


def load_corpus(path: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for file in sorted(path.glob("*.md")):
        title, sections = _split_sections(file.read_text(encoding="utf-8"))
        index = 0
        for heading, body in sections:
            if not body:
                continue
            prefix = title if heading == title else f"{title} — {heading}"
            chunks.append(
                Chunk(id=f"{file.name}#{index}", doc=file.name, heading=heading, text=f"{prefix}\n{body}")
            )
            index += 1
    return chunks
