"""DiskCachedLLM contract: hit/miss, TTL expiry, disable switch, clear(),
and the OpenAI-compat client's request/response handling (HTTP stubbed)."""

import io
import json

from causal_data_juicer.runtime.llm import DiskCachedLLM, LLMResponse, OpenAICompatClient


class CountingClient:
    model = "fake"

    def __init__(self):
        self.calls = 0

    def params(self):
        return {"model": self.model}

    def complete(self, messages):
        self.calls += 1
        return LLMResponse(text=f"reply-{self.calls}", tokens_in=1, tokens_out=1)


def test_cache_hit_never_recalls_client(tmp_path):
    inner = CountingClient()
    llm = DiskCachedLLM(inner, tmp_path / "c")
    a = llm.complete([{"role": "user", "content": "hi"}])
    b = llm.complete([{"role": "user", "content": "hi"}])
    assert inner.calls == 1
    assert not a.cached and b.cached
    assert b.dollars == 0.0


def test_ttl_expiry_refetches(tmp_path):
    inner = CountingClient()
    llm = DiskCachedLLM(inner, tmp_path / "c", ttl_seconds=0.0)  # everything expired
    llm.complete([{"role": "user", "content": "hi"}])
    llm.complete([{"role": "user", "content": "hi"}])
    assert inner.calls == 2


def test_disable_switch_bypasses_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("CDJ_LLM_CACHE", "off")
    inner = CountingClient()
    llm = DiskCachedLLM(inner, tmp_path / "c")
    llm.complete([{"role": "user", "content": "hi"}])
    llm.complete([{"role": "user", "content": "hi"}])
    assert inner.calls == 2
    assert not list((tmp_path / "c").glob("*.json"))


def test_clear_empties_cache(tmp_path):
    llm = DiskCachedLLM(CountingClient(), tmp_path / "c")
    llm.complete([{"role": "user", "content": "a"}])
    llm.complete([{"role": "user", "content": "b"}])
    assert llm.clear() == 2
    assert not list((tmp_path / "c").glob("*.json"))


def test_openai_compat_client_parses_response(monkeypatch):
    captured = {}

    class FakeResp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data)
        captured["timeout"] = timeout
        return FakeResp(
            json.dumps(
                {
                    "choices": [{"message": {"content": "the answer"}}],
                    "usage": {"prompt_tokens": 7, "completion_tokens": 3},
                }
            ).encode()
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = OpenAICompatClient(
        "http://x/v1", "m", price_in_per_mtok=1.0, price_out_per_mtok=2.0, timeout_s=9
    )
    resp = client.complete([{"role": "user", "content": "q"}])
    assert resp.text == "the answer"
    assert (resp.tokens_in, resp.tokens_out) == (7, 3)
    assert resp.dollars == (7 * 1.0 + 3 * 2.0) / 1e6
    assert captured["url"] == "http://x/v1/chat/completions"
    assert captured["body"]["model"] == "m"
    assert captured["timeout"] == 9


def test_openai_compat_client_handles_missing_usage_and_null_content(monkeypatch):
    class FakeResp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout: FakeResp(
            json.dumps({"choices": [{"message": {"content": None}}]}).encode()
        ),
    )
    resp = OpenAICompatClient("http://x/v1", "m").complete(
        [{"role": "user", "content": "a question long enough for the fallback estimator"}]
    )
    assert resp.text == ""
    assert resp.tokens_in > 0 and resp.tokens_out > 0  # estimated, never zero-negative
