"""
ARC v3 — Grammar Inducer
Mines successful (graph_signature, program) pairs to discover macros.

Algorithm (Sequitur-inspired, adapted for ARC):
  1. Collect corpus of successful programs from training
  2. Count all n-gram (bigram + trigram) frequencies
  3. For each n-gram: compute MDL saving = count*(len-1) - (len+1)
  4. Accept all n-grams with MDL saving > 0 as macro candidates
  5. For each accepted macro: fit a TriggerPattern (mean of graph signatures where this macro was effective)
  6. Return sorted macro list (highest MDL saving first)

MDL Principle (Rissanen 1978):
  The best grammar minimises |Grammar| + |Data encoded by Grammar|.
  A macro is worth adding iff its compression of the corpus exceeds its own description cost.

  mdl_saving = count * (len - 1) - (len + 1)
  Add macro iff mdl_saving > 0  →  count > (len + 1) / (len - 1)
  For bigrams (len=2): count > 3
  For trigrams (len=3): count > 2
"""

from collections import defaultdict, Counter
from typing import Optional
import numpy as np

from .rule import GrammarRule, TriggerPattern
from dsl.vocab import TOKENS


class GrammarInducer:
    def __init__(self, max_macro_len: int = 4, top_k: int = 20):
        """
        max_macro_len: longest op sequence to consider as a macro
        top_k:         maximum macros to induct per run
        """
        self.max_macro_len = max_macro_len
        self.top_k         = top_k

        # Corpus: list of (graph_signature [d], program [list[int]])
        self._corpus: list[tuple[np.ndarray, list[int]]] = []

    def add(self, graph_sig: np.ndarray, program: list[int], reward: float) -> None:
        """Add a (graph, program) pair to the corpus. Only keep rewarding episodes."""
        if reward > 0.5:   # only learn from good programs
            self._corpus.append((graph_sig.copy(), list(program)))

    def induce(self) -> list[GrammarRule]:
        """
        Run grammar induction on the current corpus.
        Returns new macro rules sorted by MDL saving (descending).
        """
        if len(self._corpus) < 4:
            return []   # need minimum corpus size

        # ── Count n-gram frequencies ────────────────────────────────────────
        ngram_counts: Counter = Counter()
        ngram_contexts: dict[tuple, list[np.ndarray]] = defaultdict(list)

        for sig, prog in self._corpus:
            for n in range(2, self.max_macro_len + 1):
                for i in range(len(prog) - n + 1):
                    gram = tuple(prog[i:i + n])
                    ngram_counts[gram] += 1
                    ngram_contexts[gram].append(sig)

        # ── Filter by MDL criterion ─────────────────────────────────────────
        candidates = []
        for gram, count in ngram_counts.items():
            rule = GrammarRule(id="__candidate__", op_sequence=list(gram))
            saving = rule.expected_mdl_saving(count)
            if saving > 0:
                candidates.append((saving, count, gram))

        if not candidates:
            return []

        # Sort by saving descending, deduplicate overlapping patterns
        candidates.sort(key=lambda x: x[0], reverse=True)
        accepted    = []
        used_tokens: set[tuple] = set()

        for saving, count, gram in candidates[:self.top_k * 3]:
            # Skip all-NOP patterns (padding artifact, not a real transformation)
            if all(op == 0 for op in gram):
                continue
            # Skip patterns that are mostly NOP (>50% NOP = padding noise)
            nop_ratio = sum(1 for op in gram if op == 0) / len(gram)
            if nop_ratio > 0.5:
                continue
            if gram in used_tokens:
                continue
            used_tokens.add(gram)

            # Build trigger pattern from mean of context signatures
            sigs = ngram_contexts[gram]
            if sigs:
                pattern_vec = np.mean(np.stack(sigs), axis=0)
                trigger = TriggerPattern(
                    vector    = pattern_vec,
                    threshold = 0.65,
                    name      = f"trigger_{'_'.join(TOKENS[o] for o in gram)}",
                )
            else:
                trigger = None

            # Strip leading/trailing NOPs (padding artifact)
            ops = list(gram)
            while ops and ops[0]  == 0: ops.pop(0)
            while ops and ops[-1] == 0: ops.pop()
            if not ops:
                continue
            gram = tuple(ops)   # use cleaned gram for ID/description

            macro_id = f"MACRO_{len(accepted):03d}_{'_'.join(TOKENS[o] for o in gram)}"
            desc     = " → ".join(TOKENS[o] for o in gram)

            rule = GrammarRule(
                id          = macro_id,
                op_sequence = list(gram),
                level       = 1,
                trigger     = trigger,
                count       = count,
                mdl_saving  = saving,
                description = desc,
            )
            accepted.append(rule)
            if len(accepted) >= self.top_k:
                break

        return accepted

    def corpus_size(self) -> int:
        return len(self._corpus)

    def clear(self) -> None:
        self._corpus.clear()
