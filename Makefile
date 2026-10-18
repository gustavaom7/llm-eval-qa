# Everyday commands. Models run locally with Ollama; `test` and `report` need none.
.PHONY: test record report gif redteam-set

test:  ## lint and every test, replaying recorded answers
	ruff check .
	pytest

record:  ## with Ollama running: record what is missing
	pytest tests/evals --mode record

report:  ## write reports/summary.md and reports/index.html from the recorded answers
	pytest tests/evals -q
	@echo "open reports/index.html"

gif:  ## render docs/demo.gif (needs .[demo])
	python scripts/make_demo_gif.py

redteam-set:  ## rebuild datasets/redteam.yaml from its seeds (needs .[redteam])
	DEEPTEAM_TELEMETRY_OPT_OUT=YES python scripts/build_redteam.py
