"""Retrieval gate: needs no model, so it runs on every push."""

import pytest

from evals.baseline import check_against_baseline
from evals.gates import retrieval_recall

pytestmark = pytest.mark.retrieval


def test_retrieval_recall_at_3(golden, retriever, budgets, gate_log, known):
    retrieved = {i.id: [c.doc for c in retriever.retrieve(i.question, 3)] for i in golden}
    result = retrieval_recall(golden, retrieved, budgets["retrieval_recall_at_3"])
    gate_log.append(result)
    check_against_baseline(result, known)
