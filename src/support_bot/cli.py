"""Command line: `support-bot ask "question" [--mode replay|record|live]`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from support_bot.bot import Bot, load_system_prompt
from support_bot.corpus import load_corpus
from support_bot.llm import LLM, LLMUnavailable, OllamaLLM
from support_bot.recorder import CassetteMissing, Recorder, RunTimeExceeded
from support_bot.retriever import Retriever


def load_config(path: Path) -> dict:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    base = path.resolve().parent
    for key in ("corpus_dir", "cassette_dir"):
        config[key] = base / config[key]
    return config


def main(argv: list[str] | None = None, llm: LLM | None = None) -> int:
    parser = argparse.ArgumentParser(prog="support-bot", description="Lumen+ support bot")
    sub = parser.add_subparsers(dest="command", required=True)
    ask = sub.add_parser("ask", help="answer one question")
    ask.add_argument("question")
    ask.add_argument(
        "--mode",
        choices=["replay", "record", "live"],
        default="replay",
        help="replay recorded answers (default), record new ones, or call the model without recording",
    )
    ask.add_argument("--k", type=int, default=None, help="number of excerpts to retrieve")
    ask.add_argument("--config", type=Path, default=Path("config.yaml"))
    args = parser.parse_args(argv)

    config = load_config(args.config)
    model = llm or OllamaLLM(config["bot_model"], host=config["ollama_host"])
    recorder = Recorder(
        model, config["cassette_dir"], mode=args.mode, time_budget_s=config["run_time_budget_minutes"] * 60
    )
    bot = Bot(
        Retriever(load_corpus(config["corpus_dir"])), recorder, load_system_prompt(), k=args.k or config["k"]
    )

    try:
        answer = bot.answer(args.question)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    except (CassetteMissing, LLMUnavailable, RunTimeExceeded) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(answer.text)
    print(f"Sources: {', '.join(answer.sources) or '(none)'}")
    print(f"Tokens: {answer.input_tokens} in / {answer.output_tokens} out · {answer.latency_ms} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
