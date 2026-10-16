import json

import httpx
import pytest

from support_bot.llm import Completion, LLMUnavailable, OllamaLLM


def test_ollama_parses_chat_response():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "hi"},
                "prompt_eval_count": 12,
                "eval_count": 3,
                "total_duration": 2_500_000_000,
            },
        )

    llm = OllamaLLM("qwen2.5:3b", transport=httpx.MockTransport(handler))
    assert llm.complete("sys", "user") == Completion("hi", 12, 3, 2500)
    assert seen["url"] == "http://localhost:11434/api/chat"
    body = seen["body"]
    assert body["stream"] is False
    assert body["model"] == "qwen2.5:3b"
    assert body["messages"] == [{"role": "system", "content": "sys"}, {"role": "user", "content": "user"}]
    assert body["options"] == {"temperature": 0, "seed": 42}


def test_ollama_unreachable_raises():
    def handler(request):
        raise httpx.ConnectError("refused")

    llm = OllamaLLM("qwen2.5:3b", transport=httpx.MockTransport(handler))
    with pytest.raises(LLMUnavailable, match="ollama serve"):
        llm.complete("sys", "user")


def test_ollama_http_error_raises_unavailable_with_body():
    llm = OllamaLLM(
        "missing:1b",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(404, json={"error": "model 'missing:1b' not found"})
        ),
    )
    with pytest.raises(LLMUnavailable, match="not found"):
        llm.complete("sys", "user")


def test_ollama_timeout_says_model_is_slow_not_down():
    def handler(request):
        raise httpx.ReadTimeout("slow")

    llm = OllamaLLM("qwen2.5:3b", transport=httpx.MockTransport(handler))
    with pytest.raises(LLMUnavailable, match="timed out") as exc:
        llm.complete("sys", "user")
    assert "ollama serve" not in str(exc.value)


def test_ollama_non_json_response_raises_unavailable():
    llm = OllamaLLM("qwen2.5:3b", transport=httpx.MockTransport(lambda r: httpx.Response(200, text="<html>")))
    with pytest.raises(LLMUnavailable, match="not valid JSON"):
        llm.complete("sys", "user")
