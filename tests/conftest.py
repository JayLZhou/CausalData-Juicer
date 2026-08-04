from pathlib import Path

import pytest

from causal_data_juicer.replay.replayer import Replayer
from causal_data_juicer.replay.sandbox import UnsafeLocalWorkspace
from causal_data_juicer.runtime.collector import Collector
from causal_data_juicer.runtime.tools import default_registry
from causal_data_juicer.runtime.verifier import PytestVerifier
from causal_data_juicer.store.blob import BlobStore


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
    return Replayer(registry, UnsafeLocalWorkspace(blobs, tmp_path / "scratch"), verifier)


@pytest.fixture
def ws_root(tmp_path) -> Path:
    p = tmp_path / "workspaces"
    p.mkdir()
    return p
