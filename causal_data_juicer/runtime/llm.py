"""LLM client layer: OpenAI-compatible endpoint + full-response disk cache.

Provider-agnostic on purpose: one client covers local vLLM and any
OpenAI-compatible commercial API.  ``DiskCachedLLM`` implements the
"LLM responses fully cached" load-bearing constraint — a cache hit never
touches the network and is charged zero new cost by callers (the
``cached`` flag on the response is how they know).
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from causal_data_juicer.sdk.schemas import digest_of


@dataclass
class LLMResponse:
    text: str
    tokens_in: int
    tokens_out: int
    cached: bool = False
    dollars: float = 0.0


class LLMClient(Protocol):
    @property
    def model(self) -> str: ...

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
        return {"model": self.model, "temperature": self.temperature, "max_tokens": self.max_tokens}

    def complete(self, messages: list[dict]) -> LLMResponse:
        payload = json.dumps({**self.params(), "messages": messages}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            body = json.loads(resp.read().decode())
        text = body["choices"][0]["message"]["content"] or ""
        usage = body.get("usage") or {}
        tokens_in = usage.get("prompt_tokens") or sum(len(m["content"]) // 4 for m in messages)
        tokens_out = usage.get("completion_tokens") or max(1, len(text) // 4)
        dollars = (tokens_in * self.price_in + tokens_out * self.price_out) / 1e6
        return LLMResponse(text=text, tokens_in=tokens_in, tokens_out=tokens_out, dollars=dollars)


class DiskCachedLLM:
    """Content-addressed response cache keyed by (params, messages).

    Cache entries may embed prompt material (repo context), so the cache
    directory is created 0700 and entries are written 0600. Controls:
    ``CDJ_LLM_CACHE=off`` disables caching entirely; ``ttl_seconds``
    (or ``CDJ_LLM_CACHE_TTL`` seconds) expires old entries; ``clear()``
    wipes the cache.
    """

    def __init__(self, client: LLMClient, cache_dir: Path, ttl_seconds: float | None = None):
        self.client = client
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.cache_dir, 0o700)
        env_ttl = os.environ.get("CDJ_LLM_CACHE_TTL")
        self.ttl_seconds = (
            ttl_seconds if ttl_seconds is not None else (float(env_ttl) if env_ttl else None)
        )
        self.disabled = os.environ.get("CDJ_LLM_CACHE", "").lower() in ("off", "0", "false")

    def clear(self) -> int:
        n = 0
        for p in self.cache_dir.glob("*.json"):
            p.unlink(missing_ok=True)
            n += 1
        return n

    @property
    def model(self) -> str:
        return self.client.model

    def _key(self, messages: list[dict]) -> str:
        params = self.client.params() if hasattr(self.client, "params") else {"model": self.model}
        return digest_of({"params": params, "messages": messages})

    def complete(self, messages: list[dict]) -> LLMResponse:
        if self.disabled:
            return self.client.complete(messages)
        path = self.cache_dir / f"{self._key(messages)}.json"
        if path.exists():
            expired = (
                self.ttl_seconds is not None
                and time.time() - path.stat().st_mtime > self.ttl_seconds
            )
            if not expired:
                data = json.loads(path.read_text())
                return LLMResponse(**{**data, "cached": True, "dollars": 0.0})
            path.unlink(missing_ok=True)
        resp = self.client.complete(messages)
        payload = json.dumps(
            {
                "text": resp.text,
                "tokens_in": resp.tokens_in,
                "tokens_out": resp.tokens_out,
                "dollars": resp.dollars,
            },
            ensure_ascii=False,
        )
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(payload)
        return resp
