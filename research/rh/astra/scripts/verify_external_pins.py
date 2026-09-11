#!/usr/bin/env python3
from pathlib import Path
import re,yaml
root=Path(__file__).resolve().parents[1]; lock=yaml.safe_load((root/"TOOLCHAIN.lock").read_text()); rx=re.compile(r"^[0-9a-f]{40}$")
vals=[lock["frontier"]["sha"],lock["frontier"]["parent_sha"],lock["lean"]["mathlib_sha"],lock["lean"]["formal_conjectures_sha"],lock["external_formal_provider"]["sha"],lock["external_formal_provider"]["original_mathlib_sha"]]; bad=[x for x in vals if not rx.fullmatch(str(x))]
if bad: print("DENY invalid pin(s):",bad); raise SystemExit(1)
print("PASS external pins syntactically exact"); print("NOTE network identity is revalidated by hosted CI")
