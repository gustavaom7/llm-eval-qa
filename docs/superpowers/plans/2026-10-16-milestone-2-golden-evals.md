# Milestone 2: Golden Evals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evaluate the Lumen+ bot against a 40-item golden dataset. Deterministic gates make the pass/fail decision and a local DeepEval judge reports quality. Bot answers and judge verdicts are recorded on a GitHub runner, then replayed in CI at zero cost.

**Architecture:** A new `evals` package next to `support_bot` holds the dataset loader, the gate functions (pure, with readable messages), the bot runner and the DeepEval judge adapter. The judge adapter sends every judge call through the existing `Recorder`. pytest suites under `tests/evals/` take a `--mode replay|record|live` option. `record.yml` installs Ollama on the runner, records, and pushes the cassettes to a `cassettes/run-<id>` branch for a PR.

**Tech Stack:** Python 3.12, pytest, DeepEval 4.3.0 (pinned exactly), Ollama (`qwen2.5:3b` bot, `qwen2.5:7b` judge), GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-16-llm-eval-qa-design.md` (sections 2.2, 3.1–3.3, 3.5, 4, 6 item 2)

## Global Constraints

- Zero cost: no paid API, no secret in any workflow. Models run only through Ollama.
- Bot model `qwen2.5:3b`, judge model `qwen2.5:7b`, both pinned in `config.yaml`.
- Recorder key = SHA-256 of (model id, system prompt, user message, model options), plus the JSON schema of a structured request. Replay is the default mode, and a missing key fails with "run the Record workflow".
- Gate thresholds live only in `budgets.yaml`, with the spec's values: `retrieval_recall_at_3: 0.90`, `required_facts_rate: 0.85`, `citation_rate: 0.95`, `max_input_tokens_per_answer: 2500`, `judge_min_mean: {faithfulness: 0.70, answer_relevancy: 0.70, policy_correctness: 0.70}`, `live_only: {p95_latency_ms: 20000}`, `run_time_budget_minutes: 60`. Forbidden claims and out-of-scope refusal are fixed at 100%.
- Dataset categories exactly `fact | policy-edge | multi-doc | out-of-scope`, and item fields exactly `id, question, category, expected_sources, must_include, must_not_include`, plus `judge` (bool, this plan).
- Judge metrics gate only on a mean below threshold. Every other judge result is reported, not blocking.
- Workflows never push to `main`. Cassettes reach `main` only through a PR.
- `DEEPEVAL_TELEMETRY_OPT_OUT=YES` everywhere DeepEval runs.
- Code style: ruff `E,F,I,UP,B`, line length 110. Every task ends with `ruff check .` and `pytest` green.

## Decisions this plan makes (deviations from the spec, for review)

1. **The judge runs on 12 items, not all of them.** Measured with a probe in this session, each judged item costs 6 judge calls (Faithfulness 3, Answer Relevancy 2, G-Eval 1). A 7B judge on a CPU runner takes about 30–60 s per call. Judging all ~34 in-scope items would take 1.5–3 h, against a 60-min budget. Items marked `judge: true` (12) get judged: 72 calls, about 35–70 min. After the first recording (Task 7), the rule is: if recording cannot finish within two dispatches, set `judge_model: qwen2.5:3b` (config only) and say so in the README. If the first run shows spare time, mark more items.
2. **Record mode reuses cassettes that already exist** instead of calling the model again. A run stopped by the time budget therefore resumes on the next dispatch, and an unchanged question is never paid for twice. A changed prompt, model or option produces a new key, so it is still re-recorded. This also retires the milestone-1 minor "re-recording rewrites latency_ms".
3. **`num_ctx` is set explicitly** (bot 4096, judge 8192). Ollama's default context window would silently truncate judge prompts, which carry ~1,000 tokens of DeepEval instructions plus the retrieved excerpts.
4. **`run_time_budget_minutes` moves from `config.yaml` to `budgets.yaml`**, so every limit lives in one file. The CLI reads it from there.
5. **Record runs push cassettes to a `cassettes/run-<run_id>` branch** as well as uploading them as an artifact, so the follow-up PR can be opened without downloading anything. The workflow never touches `main`.
6. **CI runs `-m "not quality"` until the first recording lands** (Task 7 switches it on). A `workflow_dispatch` workflow can only run once its file is on `main`, so `record.yml` has to merge before anything can be recorded.

## Review Focus

1. **The judge returns JSON that does not fit DeepEval's schema.** Expected: that item's metric is reported as "judge output unreadable" and scored 0 in the mean, and the run continues. Test in Task 5.
2. **A new or edited dataset question in replay.** Expected: one failure that names every item without a recording and says "run the Record workflow", not 40 tracebacks. Test in Task 4.
3. **A record run interrupted by the time budget.** Expected: cassettes written so far are kept, and the next run calls the model only for the rest. Test in Task 1.
4. **A `must_include` string that the corpus itself does not contain** (e.g. "two weeks" where the corpus says "14 days"). Expected: the dataset test fails before any model runs. Test in Task 2.
5. **A long judge prompt reaching Ollama without `num_ctx`.** Expected: the request body carries the configured `num_ctx`. Test in Task 1.

---

## File Structure

```
budgets.yaml                       every gate threshold and limit (new)
config.yaml                        + bot_options, judge_options, request_timeout_s, budgets_file; - run_time_budget_minutes
datasets/golden.yaml               40 golden items (new)
src/support_bot/llm.py             complete(system, user, schema=None); Ollama "format"
src/support_bot/recorder.py        schema in key; record reuses cassettes; shared start time
src/support_bot/bot.py             Answer.contexts (chunk texts, for Faithfulness)
src/support_bot/cli.py             options/timeout from config, budget from budgets.yaml
src/evals/__init__.py
src/evals/dataset.py               GoldenItem, load_golden(path), DatasetError
src/evals/gates.py                 GateResult and one function per deterministic gate
src/evals/runner.py                build_bot(...), run_bot(...), MissingRecordings
src/evals/judge.py                 RecordedJudge (DeepEvalBaseLLM), build_metrics(), judge_items()
src/evals/report.py                write_summary(path, gates, latencies)
tests/conftest.py                  --mode option, telemetry opt-out
tests/evals/conftest.py            session fixtures: config, budgets, golden, answers, judge_scores, gate collector
tests/evals/test_dataset.py        dataset consistency against the corpus (unit)
tests/evals/test_retrieval.py      recall@3 gate (marker retrieval, no model)
tests/evals/test_answers.py        facts, forbidden, refusal, citation, tokens (marker quality)
tests/evals/test_judge.py          judge means (marker quality)
tests/test_gates.py, tests/test_runner.py, tests/test_judge_adapter.py, tests/test_report.py, tests/test_workflows.py
.github/workflows/ci.yml           installs .[dev,eval]; -m "not quality" until Task 7
.github/workflows/record.yml       manual record|live + monthly live (new)
README.md                          evaluation section
```

---

### Task 1: Structured requests, resumable recording, model options from config

**Files:**
- Modify: `src/support_bot/llm.py`, `src/support_bot/recorder.py`, `src/support_bot/cli.py`, `config.yaml`, `tests/fakes.py`
- Create: `budgets.yaml` (full spec contents, see Global Constraints)
- Test: `tests/test_llm.py`, `tests/test_recorder.py`, `tests/test_cli.py`

**Interfaces:**
- Produces:
  - `LLM.complete(system: str, user: str, schema: dict | None = None) -> Completion`. The `OllamaLLM` body gets `"format": schema` only when `schema` is not None.
  - `cassette_key(model, system, user, options, schema: dict | None = None) -> str`. The payload is `[model, system, user, options, schema]`.
  - `Recorder(llm, cassette_dir, mode="replay", time_budget_s=3600, started: float | None = None)`, where `started` is a `time.monotonic()` value shared by several recorders. `Recorder.complete(system, user, schema=None)`.
  - `load_budgets(path: Path) -> dict` in `support_bot/cli.py`. `load_config` resolves `budgets_file` relative to the config file, like `corpus_dir`.
  - `config.yaml` gains `bot_options: {temperature: 0, seed: 42, num_ctx: 4096}`, `judge_options: {temperature: 0, seed: 42, num_ctx: 8192}`, `request_timeout_s: 600` and `budgets_file: budgets.yaml`, and drops `run_time_budget_minutes`.
  - `FakeLLM.complete(system, user, schema=None)` records `(system, user, schema)` in `calls`. Update the existing assertions that unpack 2-tuples.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_llm.py
def test_ollama_sends_format_only_for_structured_requests(): ...
    # capture request bodies with httpx.MockTransport
    # complete("s", "u") -> "format" not in body
    # complete("s", "u", schema={"type": "object"}) -> body["format"] == {"type": "object"}

def test_ollama_sends_configured_num_ctx():
    # OllamaLLM("m", options={"temperature": 0, "seed": 42, "num_ctx": 8192})
    # -> body["options"]["num_ctx"] == 8192

# tests/test_recorder.py
def test_key_changes_with_schema():
    assert cassette_key("m", "s", "u", {}) != cassette_key("m", "s", "u", {}, schema={"type": "object"})

def test_record_reuses_existing_cassette_without_calling(tmp_path):
    # record once with FakeLLM(default="first"), then a new Recorder in record mode with FakeLLM(default="second")
    # -> second recorder returns "first", its fake has calls == []

def test_interrupted_record_run_resumes(tmp_path):
    # Recorder(record, time_budget_s=0) after recording "q1" with a normal recorder:
    # "q1" is still returned from its cassette (no RunTimeExceeded); "q2" raises RunTimeExceeded

def test_recorders_share_start_time(tmp_path):
    # Recorder(..., mode="live", time_budget_s=10, started=time.monotonic() - 11).complete(...) raises RunTimeExceeded

# tests/test_cli.py
def test_cli_uses_bot_options_from_config(config, monkeypatch):
    # monkeypatch support_bot.cli.OllamaLLM with a recorder of its kwargs that returns a FakeLLM
    # -> options == config["bot_options"], timeout == 600
```

- [ ] **Step 2: Run them, expect failures**

Run: `pytest tests/test_llm.py tests/test_recorder.py tests/test_cli.py -v`
Expected: the new tests FAIL (unexpected keyword `schema`/`started`, or the model was called again). The existing tests still pass.

- [ ] **Step 3: Implement the interfaces above.** In record mode, a readable existing cassette is returned before the time-budget check. An unreadable one is re-recorded.

- [ ] **Step 4: Run the full suite and lint**

Run: `ruff check . && pytest -q`
Expected: all pass (43 + 6 new).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: structured requests, resumable recording, model options in config"
```

---

### Task 2: Golden dataset

**Files:**
- Create: `src/evals/__init__.py`, `src/evals/dataset.py`, `datasets/golden.yaml`
- Test: `tests/evals/__init__.py`, `tests/evals/test_dataset.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) GoldenItem(id: str, question: str, category: str, expected_sources: list[str], must_include: list[str], must_not_include: list[str], judge: bool = False)`. `load_golden(path: Path) -> list[GoldenItem]` raises `DatasetError(ValueError)` with the item id in the message for: an unknown or missing field, a category outside the four, a duplicate id, an empty question, an out-of-scope item with sources or `must_include`, an in-scope item without `expected_sources` or `must_include`, and `judge: true` on an out-of-scope item.

**Dataset rules** (the implementer writes the 40 items from the corpus):
- 16 `fact`, 12 `policy-edge`, 6 `multi-doc` (2+ expected sources each), 6 `out-of-scope` (topics the corpus never mentions, e.g. a physical store, live sports rights, a price in a currency other than USD, the CEO's name).
- Each `must_include` string is a short literal copied from one of the item's expected source documents ("14 days", "$12.99", "4 profiles"), never a paraphrase.
- `must_not_include` holds the plausible wrong claim for that question (the wrong window, the wrong plan, "phone support"). At least one per policy-edge item.
- Policy-edge items probe boundaries: 14-day refund window, 2-hours-watched rule, trial once per account and payment method, pause up to 3 months once per 12 months, 18+ account holder, family sharing on Premium only, downgrade on next billing date, 30 days' notice.
- `judge: true` on exactly 12 items: 4 fact, 5 policy-edge, 3 multi-doc.
- Ids are kebab-case and descriptive (`refund-window-edge`).

- [ ] **Step 1: Write the failing tests**

```python
DATASET = ROOT / "datasets" / "golden.yaml"

def test_golden_has_spec_distribution():
    items = load_golden(DATASET)
    counts = Counter(i.category for i in items)
    assert counts == {"fact": 16, "policy-edge": 12, "multi-doc": 6, "out-of-scope": 6}
    assert sum(i.judge for i in items) == 12

def test_expected_sources_exist_in_corpus(): ...        # every source is a file in corpus/

def test_required_facts_are_literally_in_their_sources():
    # for each item and fact: fact.lower() appears in the text of at least one expected source
    # failure message lists "<id>: '<fact>' not found in <sources>"

def test_multi_doc_items_have_two_sources(): ...

@pytest.mark.parametrize("bad, message", [
    ({"category": "trivia"}, "category"),
    ({"extra": 1}, "unknown field"),
    ({"question": "  "}, "empty question"),
])
def test_invalid_items_are_rejected_with_their_id(tmp_path, bad, message): ...

def test_duplicate_ids_are_rejected(tmp_path): ...
def test_out_of_scope_item_with_sources_is_rejected(tmp_path): ...
def test_judge_on_out_of_scope_is_rejected(tmp_path): ...
```

- [ ] **Step 2: Run them, expect failures**

Run: `pytest tests/evals/test_dataset.py -v`
Expected: FAIL with `ModuleNotFoundError: evals`.

- [ ] **Step 3: Implement `dataset.py`, then write `datasets/golden.yaml` to the rules above**

- [ ] **Step 4: Run them**

Run: `ruff check . && pytest -q`
Expected: all pass. If a literal-fact test fails, fix the dataset item, never the corpus.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: golden dataset of 40 items, checked against the corpus"
```

---

### Task 3: Deterministic gates

**Files:**
- Create: `src/evals/gates.py`
- Test: `tests/test_gates.py`

**Interfaces:**
- Consumes: `GoldenItem` (Task 2) and `Answer` (bot.py, including `contexts` from Task 4; the gates only read `text`, `sources` and `input_tokens`).
- Produces:

```python
@dataclass(frozen=True)
class GateResult:
    name: str            # "Retrieval recall@3"
    value: float         # 0..1 rate, or a count for the token gate
    threshold: float
    passed: bool
    detail: str          # "30 of 34 answers state every required fact"
    failures: list[str]  # "refund-window-edge: missing '14 days'"
    def message(self) -> str: ...

def retrieval_recall(items, retrieved: dict[str, list[str]], threshold: float) -> GateResult
def required_facts(items, answers: dict[str, Answer], threshold: float) -> GateResult
def forbidden_claims(items, answers) -> GateResult           # threshold 1.0
def out_of_scope_refusal(items, answers) -> GateResult       # threshold 1.0
def citation(items, answers, threshold: float) -> GateResult
def input_tokens(answers, max_tokens: int) -> GateResult     # value = largest seen; pass if <= max
def judge_mean(name: str, scores: dict[str, float | None], threshold: float) -> GateResult  # None counts as 0 and is listed as "judge output unreadable"
```

Rules: matching is case-insensitive substring. Recall per item = |expected ∩ retrieved| / |expected|, averaged over in-scope items. Required facts and citation cover in-scope items only. Refusal covers out-of-scope items only and checks for `support_bot.bot.REFUSAL`. Citation passes when any of `answer.sources` appears in `answer.text`.

`message()` output (readable by a non-engineer): `f"{name}: {'PASS' if passed else 'FAIL'} — {detail}; gate {threshold:.0%}"` (the token gate prints `gate {threshold:.0f} tokens`), then one line `  - <failure>` per failure, at most 10, then `  - … and N more`.

- [ ] **Step 1: Write the failing tests** — one per function with tiny synthetic items and answers, asserting value, passed and the failure strings. Plus:

```python
def test_message_is_readable():
    r = GateResult("Required facts", 0.5, 0.85, False, "1 of 2 answers state every required fact",
                   ["refund-window-edge: missing '14 days'"])
    assert r.message() == ("Required facts: FAIL — 1 of 2 answers state every required fact; gate 85%\n"
                           "  - refund-window-edge: missing '14 days'")

def test_message_truncates_after_ten_failures(): ...
def test_required_facts_ignores_case(): ...
def test_refusal_gate_fails_when_out_of_scope_item_is_answered(): ...
def test_judge_mean_counts_unreadable_as_zero_and_lists_it(): ...
```

- [ ] **Step 2: Run, expect FAIL** — `pytest tests/test_gates.py -v` → `ModuleNotFoundError: evals.gates`

- [ ] **Step 3: Implement `gates.py`**

- [ ] **Step 4: Run** — `ruff check . && pytest -q` → all pass

- [ ] **Step 5: Commit** — `git commit -m "feat: deterministic gates with readable messages"`

---

### Task 4: Bot runner and the golden suites

**Files:**
- Modify: `src/support_bot/bot.py` (add `contexts: list[str] = field(default_factory=list)` as the last field of `Answer`, filled with the retrieved chunk texts), `pyproject.toml` (markers), `.github/workflows/ci.yml`
- Create: `src/evals/runner.py`, `src/evals/report.py`, `tests/conftest.py`, `tests/evals/conftest.py`, `tests/evals/test_retrieval.py`, `tests/evals/test_answers.py`
- Test: `tests/test_runner.py`, `tests/test_report.py`, `tests/test_bot.py`

**Interfaces:**
- Consumes: Task 1 `Recorder(started=...)` and `load_budgets`, Task 2 `load_golden`, Task 3 gates.
- Produces:
  - `build_bot(config: dict, mode: str, started: float, llm: LLM | None = None) -> Bot`. It uses `OllamaLLM(config["bot_model"], host, options=config["bot_options"], timeout=config["request_timeout_s"])` behind a `Recorder`.
  - `run_bot(bot: Bot, items: list[GoldenItem]) -> dict[str, Answer]`. It collects every `CassetteMissing` and then raises `MissingRecordings(ids)`, whose message is `"No recorded answer for N items (id1, id2, …): the prompt, retriever or dataset changed. Run the Record workflow."`. Other errors propagate.
  - `write_summary(path: Path, gates: list[GateResult], latencies_ms: dict[str, list[int]], mode: str) -> None`: a Markdown table `| Gate | Result | Value | Threshold |` and, when latencies are present, `| Model | Calls | p50 ms | p95 ms | Total min |`.
  - pytest: `--mode` option (default `replay`) in `tests/conftest.py`, which also sets `os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")`. Markers `retrieval` and `quality` are registered in `pyproject.toml`. The session fixtures in `tests/evals/conftest.py` are `config`, `budgets`, `golden`, `started`, `answers` (quality only) and `gate_log` (a list that tests append to). Its finalizer writes `reports/summary.md` and the latencies taken from the recorded completions.
  - `ci.yml`: install `.[dev,eval]`, run `pytest -v -m "not quality"`, and add `env: DEEPEVAL_TELEMETRY_OPT_OUT: "YES"`.

- [ ] **Step 1: Write the failing unit tests**

```python
# tests/test_bot.py
def test_answer_carries_retrieved_chunk_texts(): ...   # contexts == [c.text for c in retrieved chunks]

# tests/test_runner.py
def test_run_bot_answers_every_item(tmp_path): ...     # FakeLLM in record mode -> one Answer per id
def test_missing_recordings_are_reported_together(tmp_path):
    # replay with an empty cassette dir over 3 in-scope items
    with pytest.raises(MissingRecordings) as exc:
        run_bot(bot, items)
    assert "3 items" in str(exc.value) and "Run the Record workflow" in str(exc.value)
    assert all(i.id in str(exc.value) for i in items)

# tests/test_report.py
def test_summary_lists_each_gate(tmp_path): ...
def test_summary_reports_p95_latency(tmp_path): ...    # [100, 200, ..., 1000] -> p95 == 1000 (nearest rank)
```

- [ ] **Step 2: Run, expect FAIL** — `pytest tests/test_bot.py tests/test_runner.py tests/test_report.py -v`

- [ ] **Step 3: Implement `bot.py` change, `runner.py`, `report.py`, conftests and markers**

- [ ] **Step 4: Write the suites**

```python
# tests/evals/test_retrieval.py  (pytestmark = pytest.mark.retrieval) — no model, runs in every CI
def test_retrieval_recall_at_3(golden, retriever, budgets, gate_log):
    retrieved = {i.id: [c.doc for c in retriever.retrieve(i.question, 3)] for i in golden}
    result = retrieval_recall(golden, retrieved, budgets["retrieval_recall_at_3"])
    gate_log.append(result)
    assert result.passed, result.message()

# tests/evals/test_answers.py  (pytestmark = pytest.mark.quality) — one test per gate, same shape:
test_required_facts, test_no_forbidden_claims, test_out_of_scope_is_refused, test_answers_cite_sources,
test_input_tokens_within_budget
```

- [ ] **Step 5: Run the retrieval gate on the real dataset**

Run: `pytest tests/evals/test_retrieval.py -v`
Expected: PASS (recall ≥ 0.90). If it fails, it is an evaluation finding. Do not reword questions to fit BM25. Record a ledger ruling, try the smallest retriever fix (stop words, stemming) with a unit test, and report the number if it still fails.

- [ ] **Step 6: Confirm replay fails readably with no cassettes**

Run: `pytest tests/evals/test_answers.py -q`
Expected: errors whose text contains "No recorded answer for 40 items" and "Run the Record workflow". This is the expected state until Task 7.

- [ ] **Step 7: Run CI's selection** — `ruff check . && pytest -q -m "not quality"` → all pass

- [ ] **Step 8: Commit** — `git commit -m "feat: golden answer suites with replayable bot runs"`

---

### Task 5: DeepEval judge through the recorder

**Files:**
- Modify: `pyproject.toml` (`eval = ["deepeval==4.3.0"]` optional extra; `.deepeval/` in `.gitignore`)
- Create: `src/evals/judge.py`, `tests/evals/test_judge.py`
- Test: `tests/test_judge_adapter.py`

**Interfaces:**
- Consumes: `Recorder.complete(system, user, schema)` (Task 1), `GoldenItem.judge` (Task 2), `judge_mean` (Task 3), the `answers` fixture (Task 4).
- Produces:
  - `class RecordedJudge(DeepEvalBaseLLM)`: `__init__(recorder: Recorder)`. `generate(prompt: str, schema: type[BaseModel] | None = None)` calls `recorder.complete("", prompt, schema.model_json_schema() if schema else None)`. It returns `schema.model_validate_json(text)` when that parses, otherwise the raw text (DeepEval then tries its own JSON repair). `a_generate` delegates to `generate`. `get_model_name()` returns the recorder's model. `load_model()` returns self.
  - `build_metrics(judge: RecordedJudge) -> dict[str, BaseMetric]`, with keys `faithfulness`, `answer_relevancy` and `policy_correctness`. They are `FaithfulnessMetric` and `AnswerRelevancyMetric` with `include_reason=False, async_mode=False`, and `GEval(name="Policy correctness", evaluation_steps=[...fixed list...], evaluation_params=[INPUT, ACTUAL_OUTPUT, EXPECTED_OUTPUT], async_mode=False)`. The G-Eval steps: "Check the answer states every fact in the expected output.", "Penalize any claim that contradicts the expected output.", "Do not penalize extra correct detail or the Sources line."
  - `judge_scores(items, answers, metrics) -> dict[str, dict[str, float | None]]`: metric → item id → score, for items with `judge: true` only. A metric that raises for an item scores `None`. `CassetteMissing` and `RunTimeExceeded` propagate.
  - Fixture `judge` in `tests/evals/conftest.py`: `Recorder(OllamaLLM(config["judge_model"], options=config["judge_options"], timeout=...), mode, started=started)`.

- [ ] **Step 1: Write the failing unit tests** (FakeLLM, no Ollama)

```python
def test_generate_sends_schema_and_returns_model(tmp_path):
    # FakeLLM(default='{"truths": ["a"]}'); judge.generate("p", schema=Truths) -> Truths(truths=["a"])
    # fake.calls[0][2] == Truths.model_json_schema()

def test_generate_returns_text_when_output_does_not_fit_schema(tmp_path): ...
def test_judge_calls_replay_from_cassettes(tmp_path): ...  # record once, replay with a fake that raises if called
def test_faithfulness_scores_through_recorded_judge(tmp_path):
    # FakeLLM answering by schema name (Truths/Claims/Verdicts JSON) -> metric.score == 1.0
def test_unreadable_judge_output_scores_none(tmp_path):
    # FakeLLM(default="not json") -> judge_scores(...)["faithfulness"][id] is None
def test_only_judge_items_are_scored(tmp_path): ...
```

`FakeLLM` needs a `responder: Callable[[str, str, dict | None], str] | None` option to answer by schema. Add it to `tests/fakes.py`.

- [ ] **Step 2: Run, expect FAIL** — `pytest tests/test_judge_adapter.py -v`

- [ ] **Step 3: Implement `judge.py`, the fixture, and `tests/evals/test_judge.py`** (marker `quality`). That file has one test per metric: `assert judge_mean(name, scores[key], budgets["judge_min_mean"][key]).passed`, with each result appended to `gate_log`.

- [ ] **Step 4: Run** — `pip install -e ".[dev,eval]" && ruff check . && pytest -q -m "not quality"` → all pass

- [ ] **Step 5: Commit** — `git commit -m "feat: DeepEval judge replayed through the recorder"`

---

### Task 6: Record workflow and README

**Files:**
- Create: `.github/workflows/record.yml`, `tests/test_workflows.py`
- Modify: `README.md`

**record.yml contract:**
- Triggers: `workflow_dispatch` with input `mode` (choice `record` | `live`, default `record`), plus `schedule: cron "17 6 1 * *"`, which runs `live`. Mode expression: `${{ github.event.inputs.mode || 'live' }}`.
- `permissions: contents: write`. No `secrets.` anywhere. `timeout-minutes: 90`. `env: DEEPEVAL_TELEMETRY_OPT_OUT: "YES"`.
- Steps:
  1. checkout, then setup-python 3.12 with pip cache.
  2. `pip install -e ".[dev,eval]"`.
  3. `curl -fsSL https://ollama.com/install.sh | sh`, then wait until `curl -sf localhost:11434/api/version` succeeds (start `ollama serve &` if the service is not up), then `ollama --version`.
  4. `ollama pull` the two models read from `config.yaml` with `python -c`.
  5. `pytest tests/evals -m "retrieval or quality" --mode $MODE -v` with `id: evals` and `continue-on-error: true`.
  6. `cat reports/summary.md >> $GITHUB_STEP_SUMMARY` (`if: always()`).
  7. upload-artifact `reports/` and `cassettes/` (`if: always()`).
  8. When the mode is `record`: `git switch -c cassettes/run-${{ github.run_id }}`, `git add cassettes`, commit as `github-actions[bot]` with message `Record cassettes (run <id>)`, `git push origin HEAD`.
  9. `if: steps.evals.outcome == 'failure'`: `exit 1`, so failing gates turn the run red after the cassettes are saved.

- [ ] **Step 1: Write the failing test** (parse YAML with `yaml.safe_load`, note the `on` key loads as `True`)

```python
def test_record_workflow_has_manual_and_monthly_triggers(): ...
def test_workflows_use_no_secrets():   # "secrets." not in either file's text
def test_record_workflow_never_pushes_to_main():
    # every line containing "git push" in record.yml targets HEAD after "git switch -c cassettes/run-"
def test_ci_skips_quality_until_first_recording():   # "-m \"not quality\"" in ci.yml
```

- [ ] **Step 2: Run, expect FAIL** — `pytest tests/test_workflows.py -v` (record.yml missing)

- [ ] **Step 3: Write `record.yml`; README gets an "Evaluation" section:** the three layers, the gate table read from `budgets.yaml` values, how to run (`pytest -m retrieval`; `pytest tests/evals --mode record` with Ollama), what the Record workflow does and how its cassettes reach `main`. Also the judge-subset decision with its measured cost, and the status line set to "milestone 2 of 4".

- [ ] **Step 4: Run** — `ruff check . && pytest -q -m "not quality"` → all pass

- [ ] **Step 5: Commit, push, open PR "Milestone 2: golden evals"** with the decisions list from this plan in its body. Merging needs the owner's approval: it is a stop under executing-plans.

---

### Task 7: First recording (after the Task 6 PR is merged)

Merging, dispatching and opening the follow-up PR are side effects outside the worktree, so the owner approves each one.

- [ ] **Step 1:** Dispatch `record.yml` on `main` with `mode: record` (GitHub MCP `actions_run_trigger`). Wait for it to finish.
- [ ] **Step 2:** Read the job summary: the gate table, the bot and judge latencies, total minutes, the Ollama version. If the run hit `RunTimeExceeded`, dispatch again on `cassettes/run-<id>` (it resumes). If two dispatches are not enough, apply decision 1: `judge_model: qwen2.5:3b`.
- [ ] **Step 3:** Fetch `cassettes/run-<id>` into the working branch. Locally, run `pytest tests/evals -m quality` in replay and check that it matches the run's summary.
- [ ] **Step 4:** Switch `ci.yml` to `pytest -v` (quality included), update `test_ci_skips_quality_until_first_recording` to assert that quality runs, and put the README's first results table in place, with the measured times and the Ollama version. Pin that version in `record.yml` (`OLLAMA_VERSION` env for install.sh).
- [ ] **Step 5:** `ruff check . && pytest -q` → all pass in replay. Commit, push, open PR "Milestone 2: first recording".
- [ ] **Step 6:** If a gate fails on real answers, report it in the PR as an evaluation finding. Don't lower a threshold or edit the dataset to get green. The owner decides whether to change the prompt (which means a new recording) or accept the result.

## Out of scope for this milestone

Red-team set, PII and money-promise checks, the full report and Pages (milestone 3). Pruning stale cassettes (milestone 3, once the prompt starts changing). Caching Ollama models between runs.
