from navier_workflow.portfolio_v1 import Lane, allocate_budget, priority_score


def test_priority_does_not_mutate_epistemic_status():
    lane = Lane("a", "TARGET", 9, 8, 7, 2, 1, "OPEN")
    before = lane.status
    assert priority_score(lane) == 21
    assert lane.status == before


def test_allocator_preserves_diversity_floor():
    lanes = [
        Lane("a", "TARGET", 10, 10, 10, 0, 0, "OPEN"),
        Lane("b", "ATTACK", 0, 0, 0, 9, 9, "OPEN"),
        Lane("c", "SURROGATE", 1, 1, 1, 4, 4, "OPEN"),
    ]
    result = allocate_budget(lanes, total_budget=30, diversity_floor=3)
    assert sum(result.values()) == 30
    assert all(value >= 3 for value in result.values())


def test_falsified_lane_gets_no_exploration_budget():
    lanes = [
        Lane("a", "TARGET", 1, 1, 1, 0, 0, "OPEN"),
        Lane("dead", "SURROGATE", 99, 99, 99, 0, 0, "FALSIFIED"),
    ]
    result = allocate_budget(lanes, total_budget=10, diversity_floor=2)
    assert result["dead"] == 0
    assert result["a"] == 10
