"""Canary-secret suite: nothing secret-shaped may enter an LLM prompt.

Exists because `_repo_context` used to inline *every* small text file —
`.env` contents and symlinked host files walked straight into prompts.
"""
import os
import stat

import pytest

from causal_data_juicer.runtime.context import (
    build_context,
    context_manifest,
    redact_secrets,
)

CANARY_ENV = "CDJ_CANARY_ENV_dc0ffee1"
CANARY_HOST = "CDJ_CANARY_HOST_5ecre7"
CANARY_AWS = "AKIA" + "ZZZZCANARY0MEOW1"


@pytest.fixture()
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    (r / "app.py").write_text("def add(a, b):\n    return a + b\n")
    (r / "README.md").write_text("A demo repo.")
    (r / ".env").write_text(f"DB_PASSWORD={CANARY_ENV}\n")
    (r / "id_rsa").write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n")
    (r / "server.pem").write_text("-----BEGIN PRIVATE KEY-----\nxyz\n-----END PRIVATE KEY-----\n")
    (tmp_path / "host_secret.txt").write_text(CANARY_HOST)
    os.symlink(tmp_path / "host_secret.txt", r / "notes.txt")   # symlink to host file
    return r


def test_env_file_never_enters_context(repo):
    ctx = build_context(repo)
    assert CANARY_ENV not in ctx
    assert ".env" not in context_manifest(repo)


def test_symlinked_host_file_never_enters_context(repo):
    ctx = build_context(repo)
    assert CANARY_HOST not in ctx
    assert "notes.txt" not in context_manifest(repo)


def test_key_material_never_enters_context(repo):
    ctx = build_context(repo)
    assert "PRIVATE KEY" not in ctx
    for name in ("id_rsa", "server.pem"):
        assert name not in context_manifest(repo)


def test_allowed_code_still_enters(repo):
    ctx = build_context(repo)
    assert "def add(a, b):" in ctx
    assert "app.py" in context_manifest(repo)


def test_secrets_inside_allowed_files_are_redacted(repo):
    (repo / "config.py").write_text(
        f'AWS_KEY = "{CANARY_AWS}"\n'
        'API_KEY = "supersecretvalue123"\n'
        "NORMAL = 42\n")
    ctx = build_context(repo)
    assert CANARY_AWS not in ctx
    assert "supersecretvalue123" not in ctx
    assert "NORMAL = 42" in ctx


def test_high_entropy_token_is_redacted():
    tok = "9fK2mQ8xLpZ4vR7cN1jW5tY0bH3dG6sA"
    assert tok not in redact_secrets(f"value = {tok}")
    prose = "the determinism control branch must reproduce the recorded outcome"
    assert redact_secrets(prose) == prose


def test_manifest_matches_context_exactly(repo):
    ctx = build_context(repo)
    for name in context_manifest(repo):
        assert f"--- {name} ---" in ctx


def test_llm_cache_written_0600(tmp_path):
    from causal_data_juicer.runtime.llm import DiskCachedLLM, LLMResponse

    class Fake:
        model = "fake"
        def complete(self, messages):
            return LLMResponse(text="ok", tokens_in=1, tokens_out=1, dollars=0.0)

    cache = tmp_path / "cache"
    llm = DiskCachedLLM(Fake(), cache)
    llm.complete([{"role": "user", "content": "hi"}])
    assert stat.S_IMODE(cache.stat().st_mode) == 0o700
    entries = list(cache.glob("*.json"))
    assert entries and all(
        stat.S_IMODE(e.stat().st_mode) == 0o600 for e in entries)
