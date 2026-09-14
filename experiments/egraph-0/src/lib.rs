//! EGRAPH-0 — equality saturation over the von Mangoldt shared-scale slice.
//!
//! Epistemic tier: **T1** (empirical). What is measured here is the behaviour
//! of two search procedures on one expression, not a theorem about all
//! expressions.
//!
//! ## The expression
//!
//! The AEGIS analytic line carries the von Mangoldt amplitude `Λ(q)/√q` and
//! finite sums of it under a shared scale `c` (see
//! `canonical_von_mangoldt_finite_sum_shared_scale_derivative_constructive_v1`).
//! The reduction under test is the cancellation of that shared scale:
//!
//! ```text
//!   (c · Λ(q)) / (c · √q)   ⟶   Λ(q) / √q
//! ```
//!
//! ## Soundness of the rule set
//!
//! `nz` is a **constructor, not a predicate**: `(nz x)` *denotes* a nonzero
//! scalar. Cancellation is therefore sound by construction rather than by a
//! side condition that a later edit could silently drop, and an untagged
//! symbol does not cancel. `tests::nonzero_tag_is_load_bearing` asserts
//! exactly that difference, so the guard cannot decay into decoration.
//!
//! ## What this spike does and does not claim
//!
//! It claims: on this expression, greedy cost-decreasing rewriting sits at a
//! strict local minimum, while equality saturation reaches the canonical form
//! at iteration 5 and holds it for every larger budget.
//!
//! It does **not** claim the e-graph saturates. Measured: it does not.
//! `cancel-nz` puts `1` in the same e-class as a product, so `inv-distributes`
//! keeps finding fresh `inv` towers and the run ends on egg's iteration limit,
//! not on `StopReason::Saturated`. `tests::the_rule_set_does_not_saturate`
//! asserts that, so the limitation cannot quietly stop being true. The optimum
//! is reached long before the budget runs out either way — which is the point:
//! equality saturation does not need to saturate to beat a greedy rewriter that
//! cannot take a single step.
//!
//! It does **not** claim the other half of the usual greedy failure story —
//! divergence in an associativity/commutativity rewriting loop. The greedy
//! baseline below is modelled on top of e-graphs, which already quotient by
//! commutativity, so it cannot exhibit AC-oscillation by construction.
//! Demonstrating that would need a separate term-level rewriter and is out of
//! this spike's scope. Modelling it on e-graphs is deliberate: it keeps one
//! source of truth for the rules, and it makes the baseline *stronger* than a
//! textbook greedy rewriter (each step applies a rule at every site at once
//! and keeps the best result), so the local minimum is not an artefact of a
//! weak baseline.

use egg::{
    rewrite, AstSize, Extractor, Id, Language, RecExpr, Rewrite, Runner, StopReason, Symbol,
};

egg::define_language! {
    /// The fragment of the analytic language this spike reasons about.
    pub enum Aegis {
        "*" = Mul([Id; 2]),
        "/" = Div([Id; 2]),
        "inv" = Inv([Id; 1]),
        "sqrt" = Sqrt([Id; 1]),
        "Lambda" = Lambda([Id; 1]),
        "nz" = Nz([Id; 1]),
        Num(i64),
        Sym(Symbol),
    }
}

/// Every rule is an equality over the intended reading of the language.
pub fn rules() -> Vec<Rewrite<Aegis, ()>> {
    vec![
        rewrite!("div-to-mul-inv";  "(/ ?a ?b)"           => "(* ?a (inv ?b))"),
        rewrite!("mul-inv-to-div";  "(* ?a (inv ?b))"     => "(/ ?a ?b)"),
        rewrite!("inv-distributes"; "(inv (* ?a ?b))"     => "(* (inv ?a) (inv ?b))"),
        rewrite!("mul-comm";        "(* ?a ?b)"           => "(* ?b ?a)"),
        rewrite!("mul-assoc-r";     "(* (* ?a ?b) ?c)"    => "(* ?a (* ?b ?c))"),
        rewrite!("mul-assoc-l";     "(* ?a (* ?b ?c))"    => "(* (* ?a ?b) ?c)"),
        // sound because `(nz c)` denotes a nonzero scalar
        rewrite!("cancel-nz";       "(* (nz ?c) (inv (nz ?c)))" => "1"),
        rewrite!("mul-one";         "(* 1 ?a)"            => "?a"),
    ]
}

/// Tree size — the same measure as [`AstSize`], computed on a term.
pub fn cost(expr: &RecExpr<Aegis>) -> usize {
    fn go(expr: &RecExpr<Aegis>, id: Id) -> usize {
        1 + expr[id]
            .children()
            .iter()
            .map(|child| go(expr, *child))
            .sum::<usize>()
    }
    go(expr, Id::from(expr.as_ref().len() - 1))
}

/// Apply one rule at every site it matches, then extract the cheapest term.
///
/// This is one greedy step, granted more power than a textbook greedy
/// rewriter: it never has to choose *where* to apply the rule.
fn best_after_one_rule(expr: &RecExpr<Aegis>, rule: &Rewrite<Aegis, ()>) -> RecExpr<Aegis> {
    let runner = Runner::default()
        .with_iter_limit(1)
        .with_expr(expr)
        .run(std::slice::from_ref(rule));
    let root = runner.roots[0];
    Extractor::new(&runner.egraph, AstSize).find_best(root).1
}

/// The RED baseline: take any single-rule step that strictly lowers the cost;
/// stop when none does.
///
/// Returns the term it halts on and the number of steps it took.
pub fn greedy_cost_decreasing(
    start: &RecExpr<Aegis>,
    rules: &[Rewrite<Aegis, ()>],
    max_steps: usize,
) -> (RecExpr<Aegis>, usize) {
    let mut current = start.clone();
    let mut steps = 0;
    while steps < max_steps {
        let mut best: Option<RecExpr<Aegis>> = None;
        for rule in rules {
            let candidate = best_after_one_rule(&current, rule);
            let improves = cost(&candidate) < cost(&current);
            let beats_best = best.as_ref().is_none_or(|b| cost(&candidate) < cost(b));
            if improves && beats_best {
                best = Some(candidate);
            }
        }
        match best {
            Some(next) => {
                current = next;
                steps += 1;
            }
            None => break,
        }
    }
    (current, steps)
}

/// What one saturation run establishes.
pub struct Saturation {
    pub best: RecExpr<Aegis>,
    pub best_cost: usize,
    pub saturated: bool,
    pub iterations: usize,
    pub eclasses: usize,
    pub enodes: usize,
}

/// The GREEN procedure: run equality saturation, then extract the cheapest
/// equivalent term.  `iter_limit` of `None` uses egg's default.
pub fn saturate(
    start: &RecExpr<Aegis>,
    rules: &[Rewrite<Aegis, ()>],
    iter_limit: Option<usize>,
) -> Saturation {
    let mut runner = Runner::default();
    if let Some(limit) = iter_limit {
        runner = runner.with_iter_limit(limit);
    }
    let runner = runner.with_expr(start).run(rules);
    let root = runner.roots[0];
    let (best_cost, best) = Extractor::new(&runner.egraph, AstSize).find_best(root);
    Saturation {
        best,
        best_cost,
        saturated: matches!(runner.stop_reason, Some(StopReason::Saturated)),
        iterations: runner.iterations.len(),
        eclasses: runner.egraph.number_of_classes(),
        enodes: runner.egraph.total_number_of_nodes(),
    }
}

/// Are the two terms in one e-class after saturation?
pub fn equivalent(a: &RecExpr<Aegis>, b: &RecExpr<Aegis>, rules: &[Rewrite<Aegis, ()>]) -> bool {
    let runner = Runner::default().with_expr(a).with_expr(b).run(rules);
    let (left, right) = (runner.roots[0], runner.roots[1]);
    runner.egraph.find(left) == runner.egraph.find(right)
}

/// [`best_after_one_rule`], exposed so the RED test can state the local
/// minimum one rule at a time instead of as a summary.
pub fn best_after_one_rule_public(
    expr: &RecExpr<Aegis>,
    rule: &Rewrite<Aegis, ()>,
) -> RecExpr<Aegis> {
    best_after_one_rule(expr, rule)
}
