"""
ARC v3 — Macro Library
Registry of all learned grammar rules.

Starts with Level-0 primitives (the 11 DSL ops).
GrammarInducer adds Level-1 macros after each induction cycle.
Level-2 meta-macros are induced from Level-1 macro sequences.

The library is the grammar G.
A program is a sequence of rule IDs drawn from G.
MDL(program | G) = len(program_in_rule_ids) * log2(|G|)
"""

import json
import numpy as np
from pathlib import Path
from typing import Optional

from .rule import GrammarRule, TriggerPattern
from dsl.vocab import TOKENS, N_TOKENS


class MacroLibrary:
    def __init__(self):
        self._rules: dict[str, GrammarRule] = {}
        self._install_primitives()

    def _install_primitives(self) -> None:
        for op_id, name in TOKENS.items():
            rule = GrammarRule(
                id          = name,
                op_sequence = [op_id],
                level       = 0,
                description = f"Primitive: {name}",
            )
            self._rules[name] = rule

    # ── Read ─────────────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._rules)

    def all_rules(self) -> list[GrammarRule]:
        return list(self._rules.values())

    def macros(self) -> list[GrammarRule]:
        return [r for r in self._rules.values() if r.level > 0]

    def primitives(self) -> list[GrammarRule]:
        return [r for r in self._rules.values() if r.level == 0]

    def get(self, rule_id: str) -> Optional[GrammarRule]:
        return self._rules.get(rule_id)

    def vocab_size(self) -> int:
        return len(self._rules)

    def rule_ids(self) -> list[str]:
        return list(self._rules.keys())

    # ── Write ─────────────────────────────────────────────────────────────────

    def add_macro(self, rule: GrammarRule) -> bool:
        """
        Add a macro to the library.
        Returns True if added, False if duplicate or dominated.
        """
        if rule.id in self._rules:
            return False
        # Deduplicate by op_sequence
        existing_seqs = {tuple(r.op_sequence) for r in self._rules.values()}
        if tuple(rule.op_sequence) in existing_seqs:
            return False
        self._rules[rule.id] = rule
        return True

    def add_macros(self, rules: list[GrammarRule]) -> int:
        return sum(1 for r in rules if self.add_macro(r))

    def bump_count(self, rule_id: str) -> None:
        if rule_id in self._rules:
            self._rules[rule_id].count += 1

    # ── Trigger matching ──────────────────────────────────────────────────────

    def matching_rules(self, graph_sig: np.ndarray) -> list[GrammarRule]:
        """
        Return all rules whose trigger pattern fires for this graph signature.
        Primitives always match (no trigger required).
        """
        result = []
        for rule in self._rules.values():
            if rule.trigger is None or rule.trigger.matches(graph_sig):
                result.append(rule)
        return result

    # ── MDL stats ─────────────────────────────────────────────────────────────

    def mdl_grammar_cost(self) -> float:
        """
        |Grammar| in symbols: sum of all macro lengths + 1 per rule.
        Primitives are free (cost 0 — they're the base alphabet).
        """
        return sum(r.length + 1 for r in self.macros())

    def summary(self) -> dict:
        return {
            "total_rules":     len(self._rules),
            "primitives":      len(self.primitives()),
            "macros":          len(self.macros()),
            "mdl_grammar_cost": self.mdl_grammar_cost(),
            "top_macros": [
                {"id": r.id, "ops": r.description, "count": r.count, "mdl_saving": r.mdl_saving}
                for r in sorted(self.macros(), key=lambda x: x.mdl_saving, reverse=True)[:5]
            ],
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: Path) -> None:
        data = {}
        for rule_id, rule in self._rules.items():
            if rule.level == 0:
                continue   # primitives are always reconstructed from vocab
            entry = {
                "id":          rule.id,
                "op_sequence": rule.op_sequence,
                "level":       rule.level,
                "count":       rule.count,
                "mdl_saving":  rule.mdl_saving,
                "description": rule.description,
            }
            if rule.trigger is not None:
                entry["trigger"] = {
                    "vector":    rule.trigger.vector.tolist(),
                    "threshold": rule.trigger.threshold,
                    "name":      rule.trigger.name,
                }
            data[rule_id] = entry
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self, path: Path) -> int:
        if not path.exists():
            return 0
        data = json.loads(path.read_text(encoding="utf-8"))
        added = 0
        for rule_id, entry in data.items():
            trigger = None
            if "trigger" in entry:
                t = entry["trigger"]
                trigger = TriggerPattern(
                    vector    = np.array(t["vector"], dtype=np.float32),
                    threshold = t["threshold"],
                    name      = t["name"],
                )
            rule = GrammarRule(
                id          = entry["id"],
                op_sequence = entry["op_sequence"],
                level       = entry["level"],
                trigger     = trigger,
                count       = entry["count"],
                mdl_saving  = entry["mdl_saving"],
                description = entry["description"],
            )
            if self.add_macro(rule):
                added += 1
        return added
