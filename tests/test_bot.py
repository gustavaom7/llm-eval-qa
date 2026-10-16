from pathlib import Path

import pytest

from support_bot.bot import REFUSAL, Bot, load_system_prompt
from support_bot.corpus import load_corpus
from support_bot.retriever import Retriever
from tests.fakes import FakeLLM

CORPUS = Path(__file__).resolve().parents[1] / "corpus"


@pytest.fixture(scope="module")
def retriever():
    return Retriever(load_corpus(CORPUS))


def make_bot(retriever, llm=None):
    return Bot(retriever, llm or FakeLLM(), load_system_prompt(), k=3)


def test_prompt_contains_question_and_excerpts(retriever):
    llm = FakeLLM()
    question = "How long is the free trial?"
    make_bot(retriever, llm).answer(question)
    system, user, _ = llm.calls[0]
    assert system == load_system_prompt()
    assert question in user
    for chunk in retriever.retrieve(question, k=3):
        assert f"[{chunk.doc}]" in user
        assert chunk.text in user


def test_sources_are_retrieved_docs(retriever):
    question = "How do I cancel my membership?"
    expected = list(dict.fromkeys(c.doc for c in retriever.retrieve(question, k=3)))
    assert make_bot(retriever).answer(question).sources == expected


def test_no_chunks_returns_refusal_without_llm_call(retriever):
    llm = FakeLLM()
    answer = make_bot(retriever, llm).answer("asdfgh")
    assert answer.text == REFUSAL
    assert answer.sources == []
    assert (answer.input_tokens, answer.output_tokens) == (0, 0)
    assert llm.calls == []


@pytest.mark.parametrize("question", ["", "   ", "\n"])
def test_empty_question_raises(retriever, question):
    with pytest.raises(ValueError, match="empty"):
        make_bot(retriever).answer(question)


def test_usage_copied_from_completion(retriever):
    answer = make_bot(retriever).answer("How long is the free trial?")
    assert (answer.input_tokens, answer.output_tokens, answer.latency_ms) == (10, 5, 7)
    assert answer.text == "fake answer"


def test_system_prompt_contains_refusal():
    assert REFUSAL in load_system_prompt()
