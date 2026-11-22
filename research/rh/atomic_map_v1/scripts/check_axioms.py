"""Fail unless every `#print axioms` report in a Lean output uses only the standard axioms.
usage: python3 -I check_axioms.py <lean-output> <source with the #print axioms commands>"""
import re, sys

ALLOWED = {"propext", "Classical.choice", "Quot.sound"}
out, src = open(sys.argv[1]).read(), open(sys.argv[2]).read()
expected = len(re.findall(r"^\s*#print\s+axioms\b", src, re.M))
deps = re.findall(r"depends on axioms: \[([^\]]*)\]", out)
none = len(re.findall(r"does not depend on any axioms", out))
bad = sorted({a.strip() for d in deps for a in d.split(",")} - ALLOWED)
if bad:
    sys.exit(f"FAIL non-standard axioms: {', '.join(bad)}")
if len(deps) + none != expected:
    sys.exit(f"FAIL {len(deps) + none} axiom reports, expected {expected}")
print(f"axioms OK ({expected} reports)")
