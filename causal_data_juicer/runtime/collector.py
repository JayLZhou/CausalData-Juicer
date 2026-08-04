"""Trace collector: runs an agent policy step by step, snapshotting the
workspace at every step boundary and recording actions, observations and
cached LLM interactions into an ``Episode``.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Protocol

from causal_data_juicer.runtime.tools import ToolExecutor, ToolRegistry
from causal_data_juicer.runtime.verifier import Verifier
from causal_data_juicer.sdk.schemas import (
    Episode,
    LLMRecord,
    Snapshot,
    Step,
    ToolCall,
)
from causal_data_juicer.store.blob import BlobStore


class Policy(Protocol):
    """An agent policy.  Returns the next (action, llm_record) or None when
    the episode is finished."""

    def next_action(
        self, task_id: str, step_index: int, history: list[Step]
    ) -> tuple[ToolCall, LLMRecord | None] | None: ...


class Collector:
    def __init__(self, registry: ToolRegistry, blob_store: BlobStore, verifier: Verifier):
        self.registry = registry
        self.blobs = blob_store
        self.verifier = verifier

    def run_episode(
        self,
        task_id: str,
        task_description: str,
        workspace: Path,
        policy: Policy,
        workload_id: str = "",
        max_steps: int = 32,
    ) -> tuple[Episode, list[Snapshot]]:
        executor = ToolExecutor(self.registry, mode="live")
        episode = Episode(
            task_id=task_id, workload_id=workload_id, task_description=task_description
        )
        snapshots: list[Snapshot] = []

        for i in range(max_steps):
            nxt = policy.next_action(task_id, i, episode.steps)
            if nxt is None:
                break
            action, llm = nxt

            # Snapshot the state *before* the step: this is the fork point.
            digest = self.blobs.put_tree(workspace)
            snap = Snapshot(episode_id=episode.id, step_index=i, tree_digest=digest)
            snapshots.append(snap)

            t0 = time.monotonic()
            obs, obs_digest = executor.execute(workspace, action, episode.cost)
            step = Step(
                index=i,
                action=action,
                observation=obs,
                obs_digest=obs_digest,
                snapshot_id=snap.id,
                llm=llm,
                wall_time_s=time.monotonic() - t0,
            )
            if llm is not None and not llm.cached:
                episode.cost.charge_llm(llm.tokens_in, llm.tokens_out, dollars=llm.dollars)
            episode.steps.append(step)

        episode.outcome = self.verifier.evaluate(workspace, episode.cost)
        episode.final_tree_digest = self.blobs.put_tree(workspace)
        return episode, snapshots
