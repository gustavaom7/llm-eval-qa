from pathlib import Path

import pytest

from support_bot.corpus import load_corpus
from support_bot.retriever import Retriever, tokenize

CORPUS = Path(__file__).resolve().parents[1] / "corpus"


@pytest.fixture(scope="module")
def retriever():
    return Retriever(load_corpus(CORPUS))


def test_tokenize_lowercases_and_keeps_accents():
    assert tokenize("Política de REEMBOLSO?") == ["política", "de", "reembolso"]


def test_refund_question_hits_refunds_doc(retriever):
    docs = [c.doc for c in retriever.retrieve("Can I get my money back after 10 days?")]
    assert "refunds.md" in docs


def test_cancel_question_hits_cancellation_doc(retriever):
    docs = [c.doc for c in retriever.retrieve("How do I cancel my membership?")]
    assert "cancellation.md" in docs


def test_no_overlap_returns_empty(retriever):
    assert retriever.retrieve("asdfgh qwerty") == []


def test_k_limits_results(retriever):
    assert len(retriever.retrieve("plan price", k=2)) == 2


def test_plural_and_question_words_still_find_prices(retriever):
    docs = [c.doc for c in retriever.retrieve("What is the price of Standard?")]
    assert "plans-and-prices.md" in docs


def test_k_below_one_raises(retriever):
    with pytest.raises(ValueError):
        retriever.retrieve("price", k=0)
