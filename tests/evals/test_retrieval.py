"""Retrieval gate: needs no model, so it runs on every push."""

import pytest

from evals.gates import retrieval_recall

pytestmark = pytest.mark.retrieval


def test_retrieval_recall_at_3(golden, retriever, budgets, gate_log):
    retrieved = {i.id: [c.doc for c in retriever.retrieve(i.question, 3)] for i in golden}
    result = retrieval_recall(golden, retrieved, budgets["retrieval_recall_at_3"])
    gate_log.append(result)
    assert result.passed, result.message()
