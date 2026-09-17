#!/usr/bin/env node
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const registry = JSON.parse(readFileSync(".github/sota-action-pins.json", "utf8"));
const files = readdirSync(".github/workflows")
  .filter((name) => /\.ya?ml$/.test(name))
  .sort();

const rows = [];
for (const file of files) {
  const text = readFileSync(join(".github/workflows", file), "utf8");
  const regex = /^\s*(?:-\s*)?uses:\s*["']?([^"'\s#]+)["']?/gm;
  for (const match of text.matchAll(regex)) {
    const ref = match[1];
    if (ref.startsWith("./")) continue;
    const at = ref.lastIndexOf("@");
    const action = at >= 0 ? ref.slice(0, at) : ref;
    const revision = at >= 0 ? ref.slice(at + 1) : "";
    rows.push({ workflow: file, ref, action, revision, pinned: /^[0-9a-f]{40}$/.test(revision) });
  }
}

const floating = rows.filter((row) => !row.pinned);
const pinned = rows.filter((row) => row.pinned);
const floatingWorkflows = new Set(floating.map((row) => row.workflow));
const violations = [];

const managed = new Set(registry.managed_workflows);
for (const row of rows) {
  if (!managed.has(row.workflow)) continue;
  const allowed = registry.pins[row.action]?.allowed_shas;
  if (!allowed) continue;
  if (!allowed.includes(row.revision)) {
    violations.push(
      `${row.workflow}: ${row.ref} is not an allowed immutable pin for ${row.action}`,
    );
  }
}
if (floating.length > registry.baseline.floating_action_refs) {
  violations.push(`floating action refs regressed: ${floating.length} > ${registry.baseline.floating_action_refs}`);
}
if (floatingWorkflows.size > registry.baseline.floating_workflows) {
  violations.push(`floating workflows regressed: ${floatingWorkflows.size} > ${registry.baseline.floating_workflows}`);
}

console.log(JSON.stringify({
  schema: "AEGIS_CI_SUPPLY_CHAIN_AUDIT_V1",
  workflow_count: files.length,
  action_ref_count: rows.length,
  pinned_action_ref_count: pinned.length,
  floating_action_ref_count: floating.length,
  floating_workflow_count: floatingWorkflows.size,
  targeted_pin_violations: violations,
  floating_refs: [...new Set(floating.map((row) => row.ref))].sort(),
  authority_effect: "NONE"
}, null, 2));

if (violations.length) process.exit(1);
