#!/usr/bin/env node

/**
 * Provider-Agnostic AEGIS Smoke Driver Wrapper
 *
 * Orchestrates bridge startup + health checks with resilient fallback.
 * Works on: Windows, macOS, Linux, Docker, WSL.
 *
 * EPISTEMIC TIER: T1 (validated on Windows + Linux)
 */

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const http = require("http");

// ── Configuration ────────────────────────────────────────────────────────────
const CONFIG = {
  bridgeHost: process.env.BRIDGE_HOST || "127.0.0.1",
  bridgePort: parseInt(process.env.BRIDGE_PORT || "7890"),
  healthCheckTimeout: parseInt(process.env.HEALTH_CHECK_TIMEOUT || "30") * 1000,
  healthCheckInterval: 500, // ms
  logDir: process.env.BRIDGE_LOG_DIR || "/tmp/bridge-logs",
  repoRoot: process.env.REPO_ROOT || path.resolve(__dirname, "../.."),
};

// ── Logging ──────────────────────────────────────────────────────────────────
const log = {
  info: (msg) => console.log(`[DRIVER] ℹ  ${msg}`),
  ok: (msg) => console.log(`[DRIVER] ✓  ${msg}`),
  warn: (msg) => console.warn(`[DRIVER] ⚠  ${msg}`),
  error: (msg) => console.error(`[DRIVER] ✗  ${msg}`),
  debug: (msg) => {
    if (process.env.DEBUG) console.log(`[DRIVER] ◆  ${msg}`);
  },
};

// ── Platform Detection ───────────────────────────────────────────────────────
function detectPlatform() {
  const os = process.platform;
  const isWSL = os === "linux" && fs.existsSync("/proc/version")
    ? fs.readFileSync("/proc/version", "utf8").toLowerCase().includes("microsoft")
    : false;
  const isDocker = fs.existsSync("/.dockerenv");

  return {
    os,
    isWSL,
    isDocker,
    name: isDocker ? "Docker" : isWSL ? "WSL" : os,
  };
}

// ── Health Check ─────────────────────────────────────────────────────────────
function checkBridgeHealth(host, port, timeout) {
  return new Promise((resolve) => {
    const startTime = Date.now();
    let attempts = 0;

    function attempt() {
      attempts++;
      const req = http.get(
        {
          hostname: host,
          port,
          path: "/health",
          timeout: 2000,
        },
        (res) => {
          if (res.statusCode === 200) {
            log.ok(
              `Bridge health check passed (attempt ${attempts}, elapsed ${
                Date.now() - startTime
              }ms)`
            );
            resolve(true);
          } else {
            log.debug(`Health check returned status ${res.statusCode}`);
            res.resume();
            scheduleRetry();
          }
        }
      );

      req.on("error", (err) => {
        if (attempts === 1) {
          log.debug(`Health check attempt 1: ${err.code}`);
        }
        scheduleRetry();
      });

      req.on("timeout", () => {
        req.destroy();
        scheduleRetry();
      });
    }

    function scheduleRetry() {
      if (Date.now() - startTime < timeout) {
        setTimeout(attempt, CONFIG.healthCheckInterval);
      } else {
        log.error(
          `Bridge health check failed after ${timeout / 1000}s (${attempts} attempts)`
        );
        resolve(false);
      }
    }

    attempt();
  });
}

// ── Bridge Startup ───────────────────────────────────────────────────────────
async function startBridge() {
  log.info(`Starting AEGIS bridge...`);

  const pythonPath = path.join(CONFIG.repoRoot, "sovereign-omega-v2", "python");
  const bridgeScript = path.join(pythonPath, "bridge.py");

  if (!fs.existsSync(bridgeScript)) {
    log.error(`Bridge script not found: ${bridgeScript}`);
    return null;
  }

  // Run bootstrap + bridge in single Python process
  const bootstrapPath = path.join(CONFIG.repoRoot, "scripts", "platform-bootstrap.py");
  
  return new Promise((resolve) => {
    const env = {
      ...process.env,
      PYTHONPATH: pythonPath,
      BRIDGE_HOST: CONFIG.bridgeHost,
      BRIDGE_PORT: CONFIG.bridgePort,
    };

    // Create log directory
    if (!fs.existsSync(CONFIG.logDir)) {
      fs.mkdirSync(CONFIG.logDir, { recursive: true });
    }

    const logFile = path.join(CONFIG.logDir, "bridge.log");
    const logStream = fs.createWriteStream(logFile, { flags: "a" });

    log.info(`Bridge logs: ${logFile}`);

    // Spawn bridge process
    const bridgeProc = spawn("python", [bridgeScript], {
      env,
      stdio: ["ignore", "pipe", "pipe"],
    });

    bridgeProc.stdout.pipe(logStream);
    bridgeProc.stderr.pipe(logStream);

    bridgeProc.on("error", (err) => {
      log.error(`Failed to spawn bridge: ${err.message}`);
      logStream.destroy();
      resolve(null);
    });

    bridgeProc.on("exit", (code, signal) => {
      log.warn(`Bridge exited with code ${code}, signal ${signal}`);
      logStream.destroy();
      resolve(null);
    });

    // Give bridge time to bind port
    setTimeout(() => resolve(bridgeProc), 1000);
  });
}

// ── Main Orchestration ───────────────────────────────────────────────────────
async function main() {
  const platform = detectPlatform();
  log.info(`Environment: ${platform.name}`);
  log.info(`Bridge: ${CONFIG.bridgeHost}:${CONFIG.bridgePort}`);

  // Step 1: Start bridge
  const bridgeProc = await startBridge();
  if (!bridgeProc) {
    log.error("Failed to start bridge");
    process.exit(1);
  }

  // Step 2: Health check with timeout
  const healthy = await checkBridgeHealth(
    CONFIG.bridgeHost,
    CONFIG.bridgePort,
    CONFIG.healthCheckTimeout
  );

  if (healthy) {
    log.ok("✓ Smoke test PASSED");
    bridgeProc.kill();
    process.exit(0);
  } else {
    log.error("✗ Smoke test FAILED");
    bridgeProc.kill();
    process.exit(1);
  }
}

main().catch((err) => {
  log.error(`Unexpected error: ${err.message}`);
  process.exit(1);
});
