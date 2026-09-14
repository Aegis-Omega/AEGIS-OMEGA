//! EGRAPH-0 RED→GREEN spike.
//!
//! RED  — greedy cost-decreasing rewriting halts at a strict local minimum on
//!        the shared-scale expression, and every single-rule escape route from
//!        that term costs at least as much as staying put.
//! GREEN — equality saturation reaches `Λ(q)/√q` at iteration 5 and holds it
//!        for every larger budget.  It does not saturate; that limitation is
//!        asserted rather than hidden.
//!
//! Two falsifiers guard the result: the nonzero tag must be load-bearing, and
//! saturation must not collapse terms that are not equal.

use aegis_egraph_0::{cost, equivalent, greedy_cost_decreasing, rules, saturate, Aegis};
use egg::RecExpr;

/// `(c · Λ(q)) / (c · √q)` with `c` tagged nonzero.
const SHARED_SCALE: &str = "(/ (* (nz c) (Lambda q)) (* (nz c) (sqrt q)))";
/// `Λ(q) / √q`
const CANONICAL: &str = "(/ (Lambda q) (sqrt q))";

fn parse(s: &str) -> RecExpr<Aegis> {
    s.parse().expect("expression parses")
}

// RED -------------------------------------------------------------------------

#[test]
fn red_greedy_cost_decreasing_halts_at_a_local_minimum() {
    let start = parse(SHARED_SCALE);
    assert_eq!(cost(&start), 11, "input tree size");
    assert_eq!(cost(&parse(CANONICAL)), 5, "goal tree size");

    let (halted, steps) = greedy_cost_decreasing(&start, &rules(), 1000);

    assert_eq!(
        steps, 0,
        "greedy could not take a single cost-decreasing step"
    );
    assert_eq!(halted.to_string(), SHARED_SCALE, "it halts on its input");
    assert_ne!(halted.to_string(), CANONICAL, "the goal is not reached");
    assert!(
        cost(&halted) > cost(&parse(CANONICAL)),
        "and it halts strictly above the reachable minimum: {} > 5",
        cost(&halted)
    );
}

#[test]
fn red_every_escape_route_raises_or_holds_the_cost() {
    let start = parse(SHARED_SCALE);
    let base = cost(&start);

    // Applying any single rule everywhere it matches, then extracting the
    // cheapest term, never gets below the starting cost.  That is the local
    // minimum, stated per rule rather than as a summary.
    for rule in rules() {
        let after = aegis_egraph_0::best_after_one_rule_public(&start, &rule);
        assert!(
            cost(&after) >= base,
            "rule {} lowered the cost to {} — the RED premise is wrong",
            rule.name,
            cost(&after)
        );
    }
}

// GREEN -----------------------------------------------------------------------

#[test]
fn green_equality_saturation_reaches_the_canonical_form() {
    let result = saturate(&parse(SHARED_SCALE), &rules(), None);

    assert_eq!(result.best.to_string(), CANONICAL);
    assert_eq!(result.best_cost, 5);

    eprintln!(
        "EGRAPH-0: {} iterations, {} e-classes, {} e-nodes, best cost {}",
        result.iterations, result.eclasses, result.enodes, result.best_cost
    );
}

#[test]
fn green_optimum_is_reached_at_iteration_five_and_held() {
    // Not budget luck: the optimum appears at iteration 5 of egg's default 30
    // and every larger budget still extracts it.
    let start = parse(SHARED_SCALE);
    let below: Vec<usize> = (1..=4)
        .map(|limit| saturate(&start, &rules(), Some(limit)).best_cost)
        .collect();
    assert!(
        below.iter().all(|&cost| cost > 5),
        "the optimum must not already be reachable in four iterations: {below:?}"
    );
    for limit in 5..=12 {
        assert_eq!(
            saturate(&start, &rules(), Some(limit)).best_cost,
            5,
            "budget {limit} lost the optimum"
        );
    }
}

#[test]
fn the_rule_set_does_not_saturate() {
    // A recorded limitation, asserted so it cannot silently stop being true.
    // `cancel-nz` puts `1` in an e-class that also holds a product, so
    // `inv-distributes` keeps generating fresh `inv` towers and the run ends on
    // the iteration limit.  The optimum is reached long before that.
    let result = saturate(&parse(SHARED_SCALE), &rules(), None);
    assert!(!result.saturated);
    assert_eq!(result.best_cost, 5);
}

// Falsifiers ------------------------------------------------------------------

#[test]
fn nonzero_tag_is_load_bearing() {
    let rules = rules();
    assert!(
        equivalent(&parse("(* (nz c) (inv (nz c)))"), &parse("1"), &rules),
        "a tagged nonzero scalar cancels"
    );
    assert!(
        !equivalent(&parse("(* c (inv c))"), &parse("1"), &rules),
        "an untagged symbol must NOT cancel — it may denote zero"
    );
}

#[test]
fn saturation_does_not_collapse_distinct_terms() {
    let rules = rules();
    for other in ["(Lambda q)", "(sqrt q)", "1", "(/ (sqrt q) (Lambda q))"] {
        assert!(
            !equivalent(&parse(CANONICAL), &parse(other), &rules),
            "{CANONICAL} must not be merged with {other}"
        );
    }
}
