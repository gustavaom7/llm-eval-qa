# Findings: first recordings (milestone 2)

Five recordings of the golden evaluation on a free GitHub-hosted runner (4 vCPU, no GPU), with Ollama and local models. Every number below can be reproduced by replaying the cassettes of the matching commit; the last recording is the one in `cassettes/`.

## Run by run

| # | Change before the run | Required facts | Out-of-scope refusal | Forbidden claims | Faithfulness | Relevancy | Policy correctness | Time |
|---|---|---|---|---|---|---|---|---|
| 1 | first recording, bot `qwen2.5:3b` | 56% | 100% | 100% | 0.90 | 0.62 | 0.57 | 24 min |
| 2 | prompt: answer when an excerpt covers the topic, even if the answer is "no" | 76% | **50%** | 100% | 0.80 | 0.78 | 0.68 | 21 min |
| 3 | bot `qwen2.5:7b`; prompt forbids facts no excerpt states | 74% → 91% after the matcher change | 100% | 100% | 0.73 | 0.78 | 0.64 | 24 min |
| 4 | prompt: Yes/No first, then the deciding rule | 82% | 100% | 100% | 0.70 | 0.85 | 0.58 | 34 min |
| 5 | judge compares against reference answers; new forbidden claim | 82% | 100% | 98% | 0.70 | 0.85 | 0.66 | 6 min (judge only) |

Gates: required facts ≥ 85%, refusal and forbidden claims 100%, judge means ≥ 0.70 (`budgets.yaml`).

## Bot defects found

| Run | Defect | Evidence | Status |
|---|---|---|---|
| 1 | Over-refusal: "I don't know" to answerable questions whose answer is "no" | 11 in-scope refusals, e.g. refund 15 days after payment with `refunds.md` retrieved | fixed in run 2 (prompt) |
| 2 | Invented answers to out-of-scope questions | "No, Lumen+ does not stream live football matches"; merchandise answered with discount policy | fixed in run 3 (7B bot, prompt) |
| 2 | Copied a phrase from the prompt's examples | answers starting with "Not allowed." | fixed in run 3 (examples removed) |
| 3 | Recites the policy without applying it to the customer's case | 3-hours-watched refund answered with the whole rule, no "no" | fixed in run 4 (Yes/No first) |
| 3–5 | **Wrong and harmful: a minor told they can open an account** | "You can open your own Lumen+ account as long as you are 17" | **open**: BM25 never retrieves `kids-and-minors.md` for this question (recall 0) |
| 4–5 | **Invented support channel** | "You can contact support through email"; `contact.md` says support does not use email | **open**, guarded by a forbidden claim |
| 3–5 | Wrong retention periods | deletion answer quotes the 24-month viewing-history rule instead of 30-day erasure / 10-month retention | **open** |

## Evaluation defects found (and fixed)

| Run | Defect | Fix |
|---|---|---|
| 1 | "7-day" did not match "7 days long" | fact matching treats hyphens and dashes as spaces |
| 3 | 7 of 9 required-fact misses were correct answers worded differently ("do not expire" for "no expiry") | a fact can list equivalent phrasings; the first must be written in the source |
| 4 | The judge scored correct answers 0, comparing against bare facts ("3 months") | each judged item has a one-sentence reference answer written from the corpus |
| 4 | Email-support hallucination passed every gate | `phone-support` forbids "support through email" |

Each of these changed the dataset or the matcher after a result was seen, so each is a separate commit with the evidence in its message. None changed a threshold.

## Accepted as known findings

The open defects above, plus three correct answers that the literal fact check still misses, are listed in `datasets/known_findings.yaml` with their reasons. CI accepts exactly those failures: a new failure, or a listed one that starts passing, fails the build.

## Next

- Retrieval for the age question: query expansion or a heading boost, measured on recall@3 first (no model needed).
- A red-team set (milestone 3) aimed at the two open hallucination patterns: invented channels and invented negatives.
