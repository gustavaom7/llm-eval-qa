# llm-eval-qa

[![CI](https://github.com/gustavaom7/llm-eval-qa/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/gustavaom7/llm-eval-qa/actions/workflows/ci.yml)

Testing an LLM product, not just using AI to write tests. The system under test is a small retrieval-augmented support bot for **Lumen+**, a fictional streaming subscription; the point of the repo is the evaluation pipeline around it: deterministic gates, LLM-as-judge metrics, a fixed red-team set, budgets and replayable CI. Everything runs on local open-source models with [Ollama](https://ollama.com), at zero cost.

> Status: milestone 1 of 4 (the bot). Evaluation suites arrive in milestones 2 and 3. Design: [`docs/superpowers/specs/`](docs/superpowers/specs/2026-10-16-llm-eval-qa-design.md).

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

## Tests

```bash
ruff check .
pytest
```

Unit tests use a fake model and never call Ollama. CI (`.github/workflows/ci.yml`) runs both on every push and pull request.
