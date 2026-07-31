"""M2 budget/policy/engine tests with a stub replayer (no real replays)."""
from causal_data_juicer.acquisition.budget import Budget
from causal_data_juicer.acquisition.engine import AcquisitionEngine
from causal_data_juicer.acquisition.policies import (
    AdaptivePolicy,
    Candidate,
    ExhaustivePolicy,
    RandomPolicy,
    make_policy,
)
from causal_data_juicer.sdk.schemas import (
    CausalUnit,
    CostLedger,
    Episode,
    EvidenceTier,
    Intervention,
    InterventionType,
    Outcome,
    ToolCall,
)


def _episode(task_id, family):
    ep = Episode(task_id=task_id, outcome=Outcome(success=False))
    ep.meta["family"] = family
    return ep


def _candidate(ep, source="s1"):
    return Candidate(episode=ep, intervention=Intervention(
        type=InterventionType.ACTION_REPLACE, target_step=0,
        new_action=ToolCall(tool="write_file", args={"path": "x", "content": ep.task_id}),
        source=source,
    ))


class StubReplayer:
    """Flips iff the episode's family is 'good'; charges 3 replays per call."""

    def __init__(self):
        self.calls = []

    def paired_replay(self, episode, snapshots, intervention, n_repro=3,
                      control_cache=None, early_stop_repro=False):
        self.calls.append(episode.task_id)
        flipped = episode.meta["family"] == "good"
        unit = CausalUnit(
            episode_id=episode.id, task_id=episode.task_id,
            intervention=intervention, original_outcome=episode.outcome,
            flipped=flipped, original_replay_match=True,
            tier=EvidenceTier.REPRODUCIBLE if flipped else EvidenceTier.SUGGESTED,
            repro_runs=n_repro, repro_flips=n_repro if flipped else 0,
            cost=CostLedger(replay_runs=3, wall_time_s=1.0),
        )
        return unit


def _engine():
    return AcquisitionEngine(replayer=StubReplayer(), slice_minimal=False)


def test_budget_truncates_spend():
    eps = [_episode(f"t{i}", "good") for i in range(10)]
    result = _engine().run([_candidate(e) for e in eps], [],
                           Budget(max_replays=9), ExhaustivePolicy())
    assert result.spent.replay_runs == 9
    assert result.candidates_processed == 3  # 3 replays each


def test_curve_is_monotone_and_complete():
    eps = [_episode(f"t{i}", "good" if i % 2 else "bad") for i in range(6)]
    result = _engine().run([_candidate(e) for e in eps], [], Budget(), ExhaustivePolicy())
    assert len(result.curve) == 6
    units = [p["validated_units"] for p in result.curve]
    assert units == sorted(units)
    assert result.curve[-1]["validated_units"] == 3


def test_adaptive_prefers_uncovered_episodes_and_good_families():
    good = [_episode(f"g{i}", "good") for i in range(3)]
    bad = [_episode(f"b{i}", "bad") for i in range(3)]
    # two candidates per episode: after a flip, the second candidate for
    # that episode should be deprioritized vs uncovered episodes
    candidates = []
    for e in good + bad:
        candidates.extend([_candidate(e, "s1"), _candidate(e, "s2")])
    engine = _engine()
    result = engine.run(list(candidates), [], Budget(max_replays=18), AdaptivePolicy())
    processed = engine.replayer.calls
    # first 6 picks must all be distinct episodes (singleton rule)
    assert len(set(processed[:6])) == 6


def test_adaptive_ucb_spends_where_flips_happen():
    good = [_episode(f"g{i}", "good") for i in range(4)]
    bad = [_episode(f"b{i}", "bad") for i in range(4)]
    candidates = [_candidate(e) for e in good + bad]
    engine = _engine()
    # budget for only 6 of 8 candidates; after sampling both families,
    # UCB should hold on to the flipping family
    result = engine.run(list(candidates), [], Budget(max_replays=18), AdaptivePolicy())
    validated = len(result.validated())
    assert result.candidates_processed == 6
    assert validated >= 3  # random order would average 3; UCB must not do worse


def test_random_policy_is_seed_deterministic():
    eps = [_episode(f"t{i}", "good") for i in range(5)]
    cands = [_candidate(e) for e in eps]
    e1, e2 = _engine(), _engine()
    e1.run(list(cands), [], Budget(), RandomPolicy(seed=7))
    e2.run(list(cands), [], Budget(), RandomPolicy(seed=7))
    assert e1.replayer.calls == e2.replayer.calls


def test_make_policy_specs():
    assert make_policy("exhaustive").name == "exhaustive"
    assert make_policy("random:3").seed == 3
    assert make_policy("adaptive").name == "adaptive"
