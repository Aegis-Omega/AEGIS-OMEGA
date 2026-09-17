#!/usr/bin/env node
import { readFileSync } from "node:fs";

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function requireInvariant(condition, message) {
  if (!condition) {
    throw new Error(`SOTA_FOUNDATION_VIOLATION: ${message}`);
  }
}

const expectedNode = readFileSync(".node-version", "utf8").trim();
const pkg = readJson("package.json");
const lock = readJson("package-lock.json");
const devcontainer = readJson(".devcontainer/devcontainer.json");
const lockRoot = lock.packages?.[""];

requireInvariant(expectedNode === "24.21.0", ".node-version must pin Node 24.21.0 LTS");
requireInvariant(pkg.private === true, "root package must be private");
requireInvariant(pkg.packageManager === "npm@11.19.0", "root packageManager must be npm@11.19.0");
requireInvariant(pkg.engines?.node === "24.21.x", "root engines.node must be 24.21.x");
requireInvariant(pkg.engines?.npm === "11.19.x", "root engines.npm must be 11.19.x");
requireInvariant(pkg.devDependencies?.concurrently === "10.0.3", "concurrently must be exact-pinned");
requireInvariant(!JSON.stringify(pkg).includes('"latest"'), "root package.json must not use latest ranges");
requireInvariant(Array.isArray(pkg.workspaces) && pkg.workspaces.length === 1 && pkg.workspaces[0] === "backend",
  "root workspace set must be exactly [backend]");

requireInvariant(lockRoot, "package-lock root package is missing");
requireInvariant(JSON.stringify(lockRoot.workspaces) === JSON.stringify(pkg.workspaces),
  "package-lock root workspaces must equal package.json workspaces");
requireInvariant(lockRoot.devDependencies?.concurrently === pkg.devDependencies.concurrently,
  "package-lock root concurrently range must equal package.json");
requireInvariant(lockRoot.engines?.node === pkg.engines.node && lockRoot.engines?.npm === pkg.engines.npm,
  "package-lock root engines must equal package.json");
requireInvariant(!lock.packages?.frontend, "package-lock must not retain removed frontend workspace metadata");

requireInvariant(devcontainer.name === "AEGIS Omega", "devcontainer must declare canonical name");
requireInvariant(typeof devcontainer.image === "string" && devcontainer.image.length > 0,
  "devcontainer image must be declared");
requireInvariant(devcontainer.features?.["ghcr.io/devcontainers/features/aws-cli:1"],
  "devcontainer aws-cli feature must live inside the features object");

console.log(JSON.stringify({
  contract: "AEGIS_SOTA_FOUNDATION_V1",
  node: expectedNode,
  npm: pkg.packageManager,
  workspace_count: pkg.workspaces.length,
  lockfile_version: lock.lockfileVersion,
  devcontainer_valid: true,
  floating_root_dependencies: false,
  authority_effect: "NONE"
}));
