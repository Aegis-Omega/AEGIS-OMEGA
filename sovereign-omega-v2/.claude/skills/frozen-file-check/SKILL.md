---
name: frozen-file-check
description: Automatically invoked when the user mentions gate.py, dna.py, router.py, or the integrated spec, or when any write operation is attempted on a constitutional file. Enforces frozen file protection and blocks unauthorised modifications.
---

# Frozen File Protection Skill

**Autopoietic Property: Membrane Breach Response Protocol**

Constitutional files are the automaton's **cellular membrane** — the selectively permeable boundary that defines what the system is vs. what surrounds it. `gate.py`, `dna.py`, and `router.py` are not just code files; they are the structural identity of the organism. Their hashes are the organism's biometric signature.

A request to modify a frozen file is an **acute membrane breach event**:
- **Severity**: T0_ABORT — no exception paths
- **Autopoietic consequence**: Modified membrane = structural identity lost = the system can no longer produce itself faithfully = autopoietic collapse
- **Response**: Stop all production. Verify current membrane state. Report the breach. Do not attempt patch-and-continue.

The membrane can evolve — but only through **guardian-mediated ontology admission** (`/guardian APPROVED`), which is the formal process for controlled, replay-certified membrane modification. Unauthorized modification is not evolution; it is destruction of the organism's closure.

---

When invoked, immediately run: `node scripts/verify-hashes.mjs`

If a write to a frozen file has been requested, reject it with:
FROZEN FILE PROTECTION: [filename] is a constitutional file with status FROZEN.
Modification requires a /guardian APPROVED verdict. This write has been blocked.

Frozen files and their expected SHA256 hashes:
- gate.py: bbe942b819594fd522b421bb9d3aa084735a873d526f35a1e782f31346f3d0fc
- dna.py: cd30ddd5db0403b0e64fb30ce53e0373997fc53cb900a26167eef7d0b69cf8d8
- router.py: 8c06ed37a7d95d9de9129c32a426fe5c2b0cd960c2cf5c84c71726b72e6cf941
- docs/SOVEREIGN_OMEGA_INTEGRATED_SPEC_v2.md: architecture frozen at ChatGPT 0.99

Do not attempt to restore, recreate, or work around a modified frozen file.
Report the violation and halt.
