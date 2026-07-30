"""LLM client layer: OpenAI-compatible endpoint + full-response disk cache.

Provider-agnostic on purpose: one client covers local vLLM and any
OpenAI-compatible commercial API.  ``DiskCachedLLM`` implements the
"LLM responses fully cached" load-bearing constraint — a cache hit never
touches the network and is charged zero new cost by callers (the
``cached`` flag on the response is how they know).
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from causeforge.sdk.schemas import digest_of


@dataclass
class LLMResponse:
    text: str
    tokens_in: int
    tokens_out: int
    cached: bool = False
    dollars: float = 0.0


class LLMClient(Protocol):
    model: str

    def complete(self, messages: list[dict]) -> LLMResponse: ...


class OpenAICompatClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "EMPTY",
        temperature: float = 0.0,
        max_tokens: int = 2048,
        timeout_s: int = 180,
        price_in_per_mtok: float = 0.0,
        price_out_per_mtok: float = 0.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_s = timeout_s
        self.price_in = price_in_per_mtok
        self.price_out = price_out_per_mtok

    def params(self) -> dict:
        return {"model": self.model, "temperature": self.temperature,
                "max_tokens": self.max_tokens}

    def complete(self, messages: list[dict]) -> LLMResponse:
        payload = json.dumps({**self.params(), "messages": messages}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            body = json.loads(resp.read().decode())
        text = body["choices"][0]["message"]["content"] or ""
        usage = body.get("usage") or {}
        tokens_in = usage.get("prompt_tokens") or sum(len(m["content"]) // 4 for m in messages)
        tokens_out = usage.get("completion_tokens") or max(1, len(text) // 4)
        dollars = (tokens_in * self.price_in + tokens_out * self.price_out) / 1e6
        return LLMResponse(text=text, tokens_in=tokens_in, tokens_out=tokens_out,
                           dollars=dollars)


class DiskCachedLLM:
    """Content-addressed response cache keyed by (params, messages)."""

    def __init__(self, client: LLMClient, cache_dir: Path):
        self.client = client
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def model(self) -> str:
        return self.client.model

    def _key(self, messages: list[dict]) -> str:
        params = self.client.params() if hasattr(self.client, "params") else {"model": self.model}
        return digest_of({"params": params, "messages": messages})

    def complete(self, messages: list[dict]) -> LLMResponse:
        path = self.cache_dir / f"{self._key(messages)}.json"
        if path.exists():
            data = json.loads(path.read_text())
            return LLMResponse(**{**data, "cached": True, "dollars": 0.0})
        resp = self.client.complete(messages)
        path.write_text(json.dumps({
            "text": resp.text, "tokens_in": resp.tokens_in,
            "tokens_out": resp.tokens_out, "dollars": resp.dollars,
        }, ensure_ascii=False))
        return resp
