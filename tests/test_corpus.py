from pathlib import Path

from support_bot.corpus import load_corpus

CORPUS = Path(__file__).resolve().parents[1] / "corpus"


def test_loads_all_documents():
    docs = {c.doc for c in load_corpus(CORPUS)}
    assert len(docs) == 20
    assert all(d.endswith(".md") for d in docs)


def test_chunks_split_on_h2(tmp_path):
    (tmp_path / "a.md").write_text("# Title\n\nintro\n\n## One\nx\n\n## Two\ny\n")
    chunks = load_corpus(tmp_path)
    assert [c.heading for c in chunks] == ["Title", "One", "Two"]
    assert [c.id for c in chunks] == ["a.md#0", "a.md#1", "a.md#2"]


def test_chunk_text_keeps_document_title(tmp_path):
    (tmp_path / "a.md").write_text("# Refunds\n\nintro\n\n## Exceptions\nnone\n")
    chunks = load_corpus(tmp_path)
    assert all(c.text.startswith("Refunds") for c in chunks)
    assert chunks[1].text.startswith("Refunds — Exceptions")


def test_empty_sections_are_skipped(tmp_path):
    (tmp_path / "a.md").write_text("# Title\n\n## Empty\n\n## Full\ntext\n")
    assert [c.heading for c in load_corpus(tmp_path)] == ["Full"]


def test_ids_are_stable():
    assert [c.id for c in load_corpus(CORPUS)] == [c.id for c in load_corpus(CORPUS)]


def test_refund_facts_present():
    text = " ".join(c.text for c in load_corpus(CORPUS) if c.doc == "refunds.md")
    assert "14 days" in text
    assert "2 hours" in text
