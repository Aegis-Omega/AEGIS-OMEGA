from scripts.generate_provenance_census import (
    POST_BASELINE_BRANCHES,
    POST_BASELINE_PRS,
    REQUIRED_OPEN_POST_BASELINE_PRS,
    RemoteHead,
    partition_census_heads,
    partition_census_prs,
)


def test_pr347_branch_is_classified_post_baseline_without_mutating_frozen_150() -> None:
    baseline_fixture = [
        RemoteHead(name=f"branch-{i:03d}", sha=f"{i:040x}", protected=False)
        for i in range(150)
    ]
    constructive_trig = RemoteHead(
        name="proof/weil-constructive-prime-trig-v1",
        sha="4" * 40,
        protected=False,
    )

    baseline, live = partition_census_heads(baseline_fixture + [constructive_trig])

    assert constructive_trig.name in POST_BASELINE_BRANCHES
    assert len(baseline) == 150
    assert len(live) == 151
    assert constructive_trig not in baseline


def test_pr347_is_classified_required_open_post_baseline_without_mutating_frozen_95() -> None:
    baseline_fixture = [
        {"number": i + 1, "draft": i < 73}
        for i in range(95)
    ]
    constructive_trig_pr = {"number": 347, "draft": True}

    baseline, live = partition_census_prs(baseline_fixture + [constructive_trig_pr])

    assert 347 in POST_BASELINE_PRS
    assert REQUIRED_OPEN_POST_BASELINE_PRS == frozenset({342, 347})
    assert len(baseline) == 95
    assert sum(1 for pr in baseline if pr["draft"] is True) == 73
    assert sum(1 for pr in baseline if pr["draft"] is not True) == 22
    assert len(live) == 96
    assert constructive_trig_pr not in baseline
