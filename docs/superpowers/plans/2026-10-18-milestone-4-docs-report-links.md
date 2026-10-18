# Milestone 4: Docs, Published Report and Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the repo readable in two minutes by a hiring manager. That means:
- a finished test strategy;
- a README with a GIF of the CLI, the latest results and the trade-offs;
- the evaluation report published on GitHub Pages;
- links from the GitHub profile and the portfolio site.

One small gate closes the red-team finding about invented source names.

**Architecture:**
- **HTML report:** `report.py` writes `reports/index.html` from the same data as `summary.md`. CI on `main` deploys `reports/` to GitHub Pages.
- **GIF:** `scripts/make_demo_gif.py` runs `support-bot ask` in replay mode, so it needs no model and is reproducible. It renders the terminal frames with Pillow into `docs/demo.gif`.
- **Citation gate:** a new deterministic gate checks that every file named in a `Sources:` line exists in the corpus.
- **Cross-repo:** the profile (`gustavaom7/gustavaom7`) and the site (`gustavaom7/gustavaom7.github.io`) get a row and a card, each in its own PR.

**Tech Stack:** Python 3.12, Pillow (`demo` extra, dev-only), GitHub Actions (`actions/upload-pages-artifact`, `actions/deploy-pages`), HTML and CSS with no framework.

**Spec:** `docs/superpowers/specs/2026-10-16-llm-eval-qa-design.md` (sections 1 success criteria 3–4, 4 Report, 5, 6 item 4)

## Global Constraints

- Zero cost, no secrets. Pages is free for public repos.
- The report and the README show numbers that come from recorded runs, with the run named. Nothing is typed in by hand without its source.
- The HTML report is one static file: inline CSS, no JavaScript, no external fonts. It must read well on a phone.
- The site follows its own conventions: EN and PT strings in the `i18n` blocks of `index.html`, and its Playwright tests updated in the same PR. The site's `CLAUDE.md` and the repo's own rules win where they differ from this plan.
- Ruff `E,F,I,UP,B`, line length 110. Every task ends with `ruff check .` and `pytest` green.

## Decisions this plan makes (for review)

1. **The README results table shows the latest recorded run** (record mode calls the real models), labeled with its run number and date. The spec says "latest live-run table". A live run is still dispatched in Task 6, after merge. It is expected to break two limits: the 60-min run budget, since bot calls for the flooding attacks reach a p95 of 64 s, and the 20 s p95 latency budget. Whatever it shows is documented as a finding.
2. **The GIF is rendered by a Python script, not recorded by hand.** It needs no model (replay mode), no screen recorder and no extra binary beyond Pillow. Anyone can regenerate it, and it can never show an answer the cassettes don't contain.
3. **New gate: cited sources must exist.**
   - Every name in an answer's `Sources:` line must be a corpus file.
   - It applies to golden and red-team answers.
   - Gate: 100%. It is not critical, so `known_findings.yaml` may list failures.
   - The two red-team answers that cite `deep_context.md` are expected to fail it. They go into the baseline with the reason, which shows the baseline doing its job.
4. **A Makefile with `test`, `record`, `report` and `gif`.** The spec's README mentions `make record` / `make test`.
5. **The profile and the site link to the repo and its Pages report.** The site card says what the repo shows, with real numbers from the findings: 5 recordings, 0 critical in 44 attacks, bugs found. It makes no claims beyond the recordings.

## Review Focus

1. **Report HTML with a failing gate, a known finding and an empty red-team section:** it must still render, and a FAIL must be visible without colour alone (it carries the text "FAIL").
2. **Text from answers or findings containing `<`, `&` or `"`** (attack texts include `</excerpts>`). Everything must be HTML-escaped.
3. **A `Sources:` line with spaces, trailing punctuation or a duplicate name** ("Sources: refunds.md, refunds.md."): no false failure on real files.
4. **The Pages deploy running on a pull request:** it must deploy only from `main` and never from PRs or forks.
5. **The GIF script run without the cassettes for its questions:** it must fail with the "run the Record workflow" message, not draw a traceback into the GIF.

---

## File Structure

```
src/evals/gates.py                 + cited_sources_exist(answers, corpus_files) -> GateResult
src/evals/report.py                + write_html(path, ...) using the same inputs as write_summary
tests/evals/conftest.py            gate_log finaliser also writes reports/index.html
tests/evals/test_answers.py        + test_cited_sources_exist (golden)
tests/evals/test_redteam.py        + cited sources on attack answers
datasets/known_findings.yaml       + the two deep_context.md citations
scripts/make_demo_gif.py           replay CLI → docs/demo.gif (new)
docs/demo.gif                      (new, generated)
Makefile                           test / record / report / gif (new)
.github/workflows/ci.yml           + deploy reports/ to Pages on main
docs/test-strategy.md              full risk matrix, not-covered list
README.md                          GIF, results table, how to run, decisions and trade-offs, report link
tests/test_report.py, tests/test_gates.py, tests/test_demo_gif.py, tests/test_workflows.py
# other repos (separate PRs)
gustavaom7/gustavaom7: README.md            featured-projects row
gustavaom7/gustavaom7.github.io: index.html + tests/portfolio.spec.ts   project card EN/PT
```

---

### Task 1: Cited sources must exist

**Interfaces — Produces:**
- `cited_sources_exist(cases: list[tuple[str, str]], corpus_files: set[str], name: str = "Cited sources exist") -> GateResult`
  - `cases` is a list of `(id, answer text)`.
  - It parses the last line that starts with `Sources:`, splits on commas, and strips spaces, quotes and trailing punctuation.
  - Failures look like `"<id>: cites missing file 'deep_context.md'"`.
  - Answers without a `Sources:` line are not checked: refusals carry none, and the citation gate already covers in-scope answers.
- Suite tests: golden in `test_answers.py`; red-team in `test_redteam.py` with the name `"Cited sources exist (red-team)"`.

- [ ] **Step 1: Failing tests** (`tests/test_gates.py`):
  - `test_real_sources_pass`
  - `test_invented_source_fails_with_its_name`
  - `test_sources_line_tolerates_spaces_duplicates_and_trailing_dot`
  - `test_answer_without_sources_line_is_not_checked`
- [ ] **Step 2:** run → FAIL
- [ ] **Step 3:** Implement. Wire both suites, then replay `pytest tests/evals`.
  - Expected: golden passes.
  - Expected: red-team fails on exactly 2 items (`fake-system-policy--embedded_instruction_json`, `repeat-instructions--embedded_instruction_json`).
  - Add those 2 to `known_findings.yaml` under `"Cited sources exist (red-team)"`, with the reason.
- [ ] **Step 4:** `ruff check . && pytest -q` → all pass
- [ ] **Step 5:** commit `feat: gate that every cited source exists in the corpus`

### Task 2: HTML report and Pages

**Interfaces — Produces:**
- `write_html(path, gates, latencies_ms, mode, budgets=None, known=None, attacks=None, run_label: str = "")`. It takes the same data as `write_summary` and writes a single HTML file containing:
  - a title;
  - the run label;
  - the gate table, with PASS/FAIL as text plus a colour;
  - the failures in a `<pre>`;
  - the red-team table, known findings, latencies and budgets.
- The `gate_log` finaliser writes both `reports/summary.md` and `reports/index.html`. The run label comes from `GITHUB_RUN_ID` / `GITHUB_RUN_NUMBER` when set, and `local` otherwise.
- `ci.yml`: a new job `pages`.
  - `needs: test`, `if: github.ref == 'refs/heads/main' && github.event_name == 'push'`.
  - Permissions `pages: write` and `id-token: write`.
  - It uploads the `reports/` artifact from the test job and deploys it with `actions/deploy-pages@v4`.
  - The test job uploads `reports/` with `actions/upload-pages-artifact@v3` when on main.

- [ ] **Step 1: Failing tests:**
  - `test_html_report_lists_every_gate_with_text_status`
  - `test_html_escapes_answer_and_finding_text` (with `</excerpts>` and `&`)
  - `test_html_renders_without_red_team_or_known_findings`
  - `test_pages_deploys_only_from_main_pushes` (workflow YAML)
- [ ] **Step 2:** run → FAIL
- [ ] **Step 3:** Implement. Escape everything with `html.escape`. The CSS goes in a `<style>` block with system fonts and a table that scrolls horizontally on small screens.
- [ ] **Step 4:** `ruff check . && pytest -q` → all pass. Open `reports/index.html` in Chromium (Playwright screenshot, mobile and desktop) and look at it.
- [ ] **Step 5:** commit `feat: HTML evaluation report published to GitHub Pages from main`

### Task 3: Demo GIF and Makefile

**Interfaces — Produces:**
- `scripts/make_demo_gif.py`, with `render(commands: list[str], out: Path, config: Path) -> None`.
  - It runs each command in a subprocess, through `support-bot ask ... --mode replay`, and captures stdout.
  - It types the command character by character (frames), then prints the output.
  - Pillow draws the frames: DejaVu Sans Mono, dark background, 100×28 terminal. The GIF is written with `save_all`, a 60 ms frame time and a 2 s hold on each answer.
  - If a command exits non-zero, it raises `SystemExit` with the captured stderr. No GIF is written.
- **Commands** (all recorded today):
  1. A refund edge case: `refund-day-15`.
  2. An out-of-scope question: `ceo-name`, which gets the fixed refusal.
  3. A red-team attack: `loyal-customer-discount`.
- `Makefile`:
  - `test`: ruff + pytest.
  - `record`: pytest tests/evals with `--mode record`.
  - `report`: pytest tests/evals, then the path to `reports/index.html`.
  - `gif`: the script.
- `pyproject`: extra `demo = ["pillow>=10"]`.

- [ ] **Step 1: Failing tests** (`tests/test_demo_gif.py`, which skips without Pillow):
  - `test_render_writes_an_animated_gif` (frames > 10, size ~ 100×28 cells)
  - `test_failing_command_raises_with_its_message` (a question without a cassette)
- [ ] **Step 2:** run → FAIL
- [ ] **Step 3:** Implement. Run `make gif` and look at `docs/demo.gif`. Keep it under 2 MB; if it is larger, reduce the frames.
- [ ] **Step 4:** `ruff check . && pytest -q` → all pass
- [ ] **Step 5:** commit `feat: reproducible demo GIF from recorded answers; Makefile`

### Task 4: Test strategy and README

**Files:** `docs/test-strategy.md` (full), `README.md`

- **`docs/test-strategy.md`:**
  - Purpose and scope.
  - A risk matrix covering the spec's risks plus the ones found: policy hallucination, PII leakage, prompt injection, prompt leakage, out-of-scope answers, token/latency blow-up, model drift, retrieval miss, invented citations. For each risk:
    - likelihood (low/med/high) and impact (low/med/high), each with a one-line reason;
    - the suite and the gate.
  - How the layers fit: deterministic first, judge second, red-team third.
  - What is deliberately not covered: multi-turn, paraphrased prompt leaks, invented promo codes, load testing, non-English questions, the judge's own accuracy beyond its reasons.
  - How a change flows from PR (replay) to Record to merge.
- **`README.md`:** reorganise for a two-minute read, in this order:
  - one-paragraph pitch;
  - the GIF;
  - a results box (latest recorded run, with the run number);
  - links to the live report (Pages), findings and strategy;
  - what's inside (the three layers and the red-team, already written);
  - how to run (`make`);
  - decisions and trade-offs: zero cost/local models, BM25 over embeddings, replay CI, judge only on 12 items, the known-findings baseline, deterministic critical checks;
  - the status line set to "complete (4 of 4)".
- [ ] **Step 1:** write the docs. `ruff check . && pytest -q` → pass. Commit `docs: full test strategy; README for a two-minute read`.

### Task 5: Review, PR (llm-eval-qa)

- [ ] Final whole-branch review (fresh reviewer), fix pass, PR "Milestone 4: docs, published report, demo". The owner approves the merge.
- [ ] **After merge**, the owner enables Pages in Settings → Pages → Source: GitHub Actions; this needs a person. The first push on main then deploys the report. Check the URL `https://gustavaom7.github.io/llm-eval-qa/`.

### Task 6: Links and live run (after Task 5's merge, owner approves each)

- [ ] **Profile** (`gustavaom7/gustavaom7`, branch `claude/funny-goldberg-ltzad1`):
  - Add a featured-projects row for **llm-eval-qa**, placed first: it is the AI-testing flagship.
  - The row has a CI badge and the report link, and says what it shows in one line, with numbers from `docs/findings.md`.
  - Add the AI-evaluation stack (DeepEval, deepteam, Ollama) to the skills line.
  - Open a PR.
- [ ] **Site** (`gustavaom7/gustavaom7.github.io`):
  - Add a project card for the repo, with EN and PT strings in both `i18n` blocks. Tags: Python, DeepEval, deepteam, Ollama.
  - Its result line: "5 recordings, 0 critical in 44 attacks, harmful answer found and documented".
  - Update `tests/portfolio.spec.ts` where it counts or orders cards, then run the site's tests.
  - Open a PR.
- [ ] **Live run:**
  - Dispatch `record.yml` with `mode: live` and read the summary.
  - Add a "Latest live run" note to README and findings, with timings, the p95 versus the 20 s budget, and drift versus the recording.
  - If it fails on time or latency, the failure itself is the finding.

## Out of scope

- Fixing the open bot findings (age retrieval, email hallucination, retention mix-up).
- Model-generated attacks, multi-turn tests and embeddings.
- Any paid service.
