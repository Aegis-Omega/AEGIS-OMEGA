"""
ARC v3 — Grammar Induction Training Loop

Phase structure (repeating):
  ─────────────────────────────────────────────────────────
  Phase A  PRIMITIVE BOOTSTRAP  (steps 0 – induct_every)
    Train GrammarPolicy over primitive ops only.
    Collect (graph_sig, program, reward) into GrammarInducer corpus.

  Phase B  GRAMMAR INDUCTION    (every induct_every steps)
    Run inducer on corpus → new macros with MDL saving > 0.
    Add macros to MacroLibrary.
    Expand GrammarPolicy head to include new macros.
    Clear induction corpus (start fresh).

  Phase A again — now policy can generate macro tokens.
  ─────────────────────────────────────────────────────────

MDL convergence signal:
  mdl_total = |Grammar| + Σ len(compressed_program_i)
  As macros compress programs, mdl_total decreases.
  Plateau in mdl_total = grammar has reached its natural complexity.

Usage:
    python train_grammar.py [--steps 20000] [--arc-data ./arc_data]
                            [--induct-every 1000]
"""

import os, sys, json, argparse, time
import numpy as np
import torch
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from data.arc_loader    import ARCLoader
from model.graph_encoder import GraphEncoder
from model.graph_world_model import GraphWorldModel
from model.grammar_policy import GrammarPolicy
from model.value         import Value
from grammar.rule        import GrammarRule
from grammar.inducer     import GrammarInducer
from grammar.macro_library import MacroLibrary
from grammar.vm_grammar  import GrammarVM
from selfplay.mutate     import perturbations
from curriculum.curriculum import Curriculum
from utils               import accuracy, compute_cvs, compute_mdl
from config              import DEVICE, EMBED_DIM, MAX_PROGRAM_LEN, LR, CVS_WEIGHT, MDL_WEIGHT, STATE_PATH


def atomic_write_state(state_path: Path, metrics: dict) -> None:
    if not state_path.exists():
        return
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["arc_benchmark"] = {
            "last_run_at": datetime.now(timezone.utc).isoformat(),
            "model": "grammar_induction_v3",
            **metrics,
        }
        state["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
        tmp = state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, state_path)
    except Exception as e:
        print(f"[WARN] state.json: {e}")


# ── MDL TRACKER ──────────────────────────────────────────────────────────────

class MDLTracker:
    """Tracks grammar MDL over time: |G| + Σ|compressed programs|."""

    def __init__(self, library: MacroLibrary):
        self.library   = library
        self.history   = []
        self._prog_lens = []

    def record(self, rule_ids: list[str]) -> None:
        """Record the (rule-level) length of a generated program."""
        self._prog_lens.append(len(rule_ids))

    def compute(self) -> float:
        if not self._prog_lens:
            return float("inf")
        grammar_cost = self.library.mdl_grammar_cost()
        data_cost    = float(np.mean(self._prog_lens)) * len(self._prog_lens)
        total        = grammar_cost + data_cost
        self.history.append(total)
        self._prog_lens.clear()
        return total


# ── CONVERT RULE INDICES → RULE IDS ─────────────────────────────────────────

def indices_to_ids(indices: torch.Tensor, library: MacroLibrary) -> list[str]:
    rule_ids = library.rule_ids()
    return [rule_ids[i] if i < len(rule_ids) else "NOP" for i in indices.tolist()]


# ── TRAINING ─────────────────────────────────────────────────────────────────

def train(args):
    device = torch.device(DEVICE)
    loader = ARCLoader(path=args.arc_data)
    print(f"Loaded {len(loader)} ARC tasks from '{args.arc_data}'")

    library  = MacroLibrary()
    inducer  = GrammarInducer(max_macro_len=4, top_k=20)
    gvm      = GrammarVM(library)
    enc      = GraphEncoder(d=EMBED_DIM).to(device)
    pol      = GrammarPolicy(library, d=EMBED_DIM).to(device)
    wm       = GraphWorldModel(d=EMBED_DIM).to(device)
    val      = Value(d=EMBED_DIM).to(device)
    mdl_tr   = MDLTracker(library)
    cur      = Curriculum()

    # Load existing macro library if available
    lib_path = Path(__file__).parent / "checkpoints" / "macro_library.json"
    lib_path.parent.mkdir(exist_ok=True)
    if lib_path.exists():
        n = library.load(lib_path)
        if n:
            pol.expand_head()
            print(f"Loaded {n} macros from {lib_path}")

    def make_opt():
        return torch.optim.Adam(
            list(enc.parameters()) + list(pol.parameters()) + list(wm.parameters()), lr=LR
        )

    opt_pw = make_opt()
    opt_v  = torch.optim.Adam(val.parameters(), lr=LR)

    best_acc    = 0.0
    acc_history = []
    induct_log  = []
    t0          = time.time()

    print(f"\nGrammar size: {library.vocab_size()} rules (all primitives)")
    print(f"Induction every {args.induct_every} steps\n")

    for step in range(1, args.steps + 1):

        # ── Phase B: Grammar Induction ────────────────────────────────────
        if step % args.induct_every == 0 and inducer.corpus_size() >= 4:
            new_rules = inducer.induce()
            added     = library.add_macros(new_rules)
            if added:
                expanded  = pol.expand_head()
                # Rebuild optimizer (new parameters added)
                opt_pw = make_opt()
                mdl_cost = library.mdl_grammar_cost()
                entry = {
                    "step":        step,
                    "new_macros":  added,
                    "total_rules": library.vocab_size(),
                    "mdl_grammar": mdl_cost,
                    "top": [r.description for r in new_rules[:3]],
                }
                induct_log.append(entry)
                print(
                    f"\n[INDUCTION step={step}] +{added} macros | "
                    f"library={library.vocab_size()} rules | "
                    f"|G|={mdl_cost:.0f} | "
                    f"top: {', '.join(r.description for r in new_rules[:3])}\n"
                )
            inducer.clear()

        # ── Phase A: Policy Training ──────────────────────────────────────
        task  = cur.apply(loader.sample())
        graph = enc(task["input"], device=device)
        sig   = graph.x.mean(0).detach().cpu().numpy()   # graph signature

        # Sample grammar program
        rule_idx, logp = pol.sample(graph, max_len=MAX_PROGRAM_LEN)
        rule_ids       = indices_to_ids(rule_idx, library)

        # Execute via grammar VM (expands macros → primitives → DSLVM)
        pred = gvm.run(rule_ids, task["input"])
        acc  = accuracy(pred, task["output"])

        # Track macro usage
        for rid in rule_ids:
            library.bump_count(rid)

        # CVS
        pert_tasks = perturbations(task, n=3)
        pert_outs  = [gvm.run(rule_ids, pt["input"]) for pt in pert_tasks]
        cvs        = compute_cvs(pert_outs)

        # MDL — program length in rule-space (shorter = better with macros)
        prog_len_rules = len([r for r in rule_ids if library.get(r) and library.get(r).id != "NOP"])
        mdl_penalty    = MDL_WEIGHT * prog_len_rules

        reward = acc + CVS_WEIGHT * cvs - mdl_penalty

        # PPO
        v_est = val(graph.x.mean(0, keepdim=True)).squeeze()
        adv   = reward - v_est.item()
        loss_p = -logp * adv
        loss_v = (v_est - reward) ** 2

        opt_pw.zero_grad()
        loss_p.backward()
        torch.nn.utils.clip_grad_norm_(
            list(enc.parameters()) + list(pol.parameters()) + list(wm.parameters()), 1.0
        )
        opt_pw.step()
        opt_v.zero_grad()
        loss_v.backward()
        opt_v.step()

        # Feed inducer
        inducer.add(sig, [i for i in rule_idx.tolist()], reward)
        mdl_tr.record(rule_ids)

        acc_history.append(acc)
        best_acc = max(best_acc, acc)
        cur.update(acc)

        if step % 200 == 0:
            mean_acc = float(np.mean(acc_history[-200:]))
            mdl_val  = mdl_tr.compute()
            elapsed  = time.time() - t0
            print(
                f"step={step:6d}  acc={mean_acc:.4f}  CVS={cvs:.4f}"
                f"  MDL={mdl_val:.0f}  rules={library.vocab_size()}"
                f"  level={cur.level}  t={elapsed:.0f}s"
            )

    # ── Final metrics ─────────────────────────────────────────────────────
    mean_acc = float(np.mean(acc_history[-500:]) if acc_history else 0.0)
    hd_arc   = 1.0 - mean_acc
    summary  = library.summary()

    metrics = {
        "steps":             args.steps,
        "mean_acc":          round(mean_acc, 4),
        "hd_arc":            round(hd_arc,   4),
        "best_acc":          round(best_acc, 4),
        "grammar":           summary,
        "induction_cycles":  len(induct_log),
        "architecture":      "grammar_induction",
    }
    print("\n=== ARC v3 GRAMMAR INDUCTION — COMPLETE ===")
    print(json.dumps(metrics, indent=2))

    # Save macro library
    library.save(lib_path)
    print(f"Macro library saved: {lib_path} ({summary['macros']} macros)")

    # Atomic write to OS state
    state_path = Path(__file__).parent / STATE_PATH
    atomic_write_state(state_path, metrics)

    # Checkpoint
    ckpt_dir = Path(__file__).parent / "checkpoints"
    torch.save({
        "enc": enc.state_dict(), "pol": pol.state_dict(),
        "wm":  wm.state_dict(),  "val": val.state_dict(),
        "metrics": metrics, "induction_log": induct_log,
    }, ckpt_dir / "arc_v3_grammar_latest.pt")
    print(f"Checkpoint: {ckpt_dir / 'arc_v3_grammar_latest.pt'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ARC v3 Grammar Induction")
    parser.add_argument("--steps",         type=int, default=20000)
    parser.add_argument("--arc-data",      type=str, default="arc_data")
    parser.add_argument("--induct-every",  type=int, default=1000,
                        help="Run grammar induction every N steps")
    args = parser.parse_args()
    train(args)
