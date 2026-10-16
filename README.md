# llm-eval-qa

[![CI](https://github.com/gustavaom7/llm-eval-qa/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/gustavaom7/llm-eval-qa/actions/workflows/ci.yml)

Testing an LLM product, not just using AI to write tests. The system under test is a small retrieval-augmented support bot for **Lumen+**, a fictional streaming subscription; the point of the repo is the evaluation pipeline around it: deterministic gates, LLM-as-judge metrics, a fixed red-team set, budgets and replayable CI. Everything runs on local open-source models with [Ollama](https://ollama.com), at zero cost.

> Status: milestone 2 of 4 (golden evals). Red-team and the full report arrive in milestone 3. Design: [`docs/superpowers/specs/`](docs/superpowers/specs/2026-10-16-llm-eval-qa-design.md).

## The bot

| Piece | Where | What it does |
|---|---|---|
| Corpus | `corpus/` | 20 help-center pages: plans and prices, free trial, billing, refunds, cancellation, privacy and more |
| Retrieval | `src/support_bot/retriever.py` | BM25 over heading-based chunks; returns nothing when no word matches |
| Prompt | `src/support_bot/prompts/system.md` | Answer only from the excerpts, cite sources, fixed refusal sentence, no money promises |
| Model | `src/support_bot/llm.py` | Ollama chat API, `temperature 0`, fixed seed |
| Recorder | `src/support_bot/recorder.py` | Replays recorded answers so tests and CI need no model |

When the excerpts do not cover a question, the bot answers with one fixed sentence, so a refusal can be checked without a judge:

> I don't know based on the Lumen+ help center. Please contact Lumen+ support through the in-app chat.

## Run it

```bash
pip install -e ".[dev]"
ollama pull qwen2.5:3b          # once; models are set in config.yaml

support-bot ask "Can I get a refund 10 days after my first payment?" --mode live
```

| Mode | Calls the model | Writes `cassettes/` | Used by |
|---|---|---|---|
| `replay` (default) | no | no | pull-request CI, tests |
| `record` | yes | yes | the Record workflow, when the prompt, retriever or dataset changes |
| `live` | yes | no | monthly drift check, trying the bot locally |

In replay mode a question with no recording fails with "run the Record workflow": a change to the prompt or the retriever cannot pass CI without being evaluated.

## Evaluation

40 questions in [`datasets/golden.yaml`](datasets/golden.yaml): 16 direct facts, 12 policy edges (refund window, trial once per account, pause limits, age 18+), 6 that need two documents, and 6 out of scope. Each item names the documents that hold the answer, the facts the answer must state, and the plausible wrong claim it must not make. A test checks that every required fact is written, word for word, in its source document.

Three layers, cheapest first. Every threshold lives in [`budgets.yaml`](budgets.yaml).

| Layer | Check | Gate |
|---|---|---|
| Retrieval (no model) | an expected document is among the 3 retrieved chunks | recall@3 ≥ 90% |
| Answers (deterministic) | required facts stated | ≥ 85% of answers |
| | forbidden claim made | never |
| | out-of-scope question gets the fixed refusal | always |
| | answer names a retrieved source | ≥ 95% |
| | prompt size | ≤ 2500 input tokens |
| Judge (DeepEval, local `qwen2.5:7b`) | faithfulness, answer relevancy, policy correctness (G-Eval) | mean ≥ 0.70; individual scores are reported, not blocking |

A failing gate prints what failed in plain words, for example:

```
Required facts: FAIL — 30 of 34 answers state every required fact; gate 85%
  - refund-day-15: missing '14 days'
```

The deterministic gates decide pass or fail; a small local judge is noisy, so it only blocks on a large drop. It scores the 12 items marked `judge: true`: each judged answer costs 6 judge calls, and on a CPU runner judging every question would not fit the 60-minute run budget.

### Recording and replay

Pull requests never call a model. They replay answers recorded in `cassettes/`, keyed by a hash of the model, prompt, question and options, so a change to the prompt, retriever or dataset fails CI with "Run the Record workflow" until it is evaluated.

The [Record workflow](.github/workflows/record.yml) installs Ollama on a GitHub runner, pulls both models and runs every suite:

- `record` (manual): records only what is missing and pushes the cassettes to a `cassettes/run-<id>` branch, merged through a pull request. A run stopped by the time budget resumes when started again on that branch.
- `live` (manual, and monthly): calls the models without recording, to measure latency and catch drift.

Each run writes the gate table and the models' latencies to the job summary.

## Tests

```bash
pip install -e ".[dev,eval]"
ruff check .
pytest -m "not quality"            # unit tests and the retrieval gate
pytest tests/evals                 # all gates, replaying recorded answers
pytest tests/evals --mode record   # with Ollama running: record what is missing
```

Unit tests use a fake model and never call Ollama. CI (`.github/workflows/ci.yml`) runs lint and `pytest -m "not quality"` on every push and pull request; the quality suites join once the first recording is merged.
