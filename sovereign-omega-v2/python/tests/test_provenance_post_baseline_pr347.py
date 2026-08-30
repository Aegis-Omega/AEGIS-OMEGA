from scripts.generate_provenance_census_with_cleanup_debt import base


def test_pr347_branch_is_classified_post_baseline_without_mutating_frozen_150() -> None:
    baseline_fixture = [
        base.RemoteHead(name=f"branch-{i:03d}", sha=f"{i:040x}", protected=False)
        for i in range(150)
    ]
    constructive_trig = base.RemoteHead(
        name="proof/weil-constructive-prime-trig-v1",
        sha="4" * 40,
        protected=False,
    )

    baseline, live = base.partition_census_heads(baseline_fixture + [constructive_trig])

    assert constructive_trig.name in base.POST_BASELINE_BRANCHES
    assert len(baseline) == 150
    assert len(live) == 151
    assert constructive_trig not in baseline


def test_pr347_is_classified_required_open_post_baseline_without_mutating_frozen_95() -> None:
    baseline_fixture = [
        {"number": i + 1, "draft": i < 73}
        for i in range(95)
    ]
    constructive_trig_pr = {"number": 347, "draft": True}

    baseline, live = base.partition_census_prs(baseline_fixture + [constructive_trig_pr])

    assert 347 in base.POST_BASELINE_PRS
    assert base.REQUIRED_OPEN_POST_BASELINE_PRS == frozenset({342, 347})
    assert len(baseline) == 95
    assert sum(1 for pr in baseline if pr["draft"] is True) == 73
    assert sum(1 for pr in baseline if pr["draft"] is not True) == 22
    assert len(live) == 96
    assert constructive_trig_pr not in baseline


def test_cleanup_ref_is_explicit_zero_authority_post_baseline_debt() -> None:
    cleanup = base.RemoteHead(name="tmp-unused", sha="f" * 40, protected=False)
    baseline_fixture = [
        base.RemoteHead(name=f"branch-{i:03d}", sha=f"{i:040x}", protected=False)
        for i in range(150)
    ]

    baseline, live = base.partition_census_heads(baseline_fixture + [cleanup])

    assert cleanup.name in base.POST_BASELINE_BRANCHES
    assert len(baseline) == 150
    assert len(live) == 151
    assert cleanup not in baseline
