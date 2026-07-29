from pathlib import Path

import pytest

from causeforge.replay.replayer import Replayer
from causeforge.replay.sandbox import LocalSandbox
from causeforge.runtime.collector import Collector
from causeforge.runtime.tools import default_registry
from causeforge.runtime.verifier import PytestVerifier
from causeforge.store.blob import BlobStore


@pytest.fixture
def registry():
    return default_registry()


@pytest.fixture
def blobs(tmp_path):
    return BlobStore(tmp_path / "blobs")


@pytest.fixture
def verifier():
    return PytestVerifier()


@pytest.fixture
def collector(registry, blobs, verifier):
    return Collector(registry, blobs, verifier)


@pytest.fixture
def replayer(registry, blobs, verifier, tmp_path):
    return Replayer(registry, LocalSandbox(blobs, tmp_path / "scratch"), verifier)


@pytest.fixture
def ws_root(tmp_path) -> Path:
    p = tmp_path / "workspaces"
    p.mkdir()
    return p
