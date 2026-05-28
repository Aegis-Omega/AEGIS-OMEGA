#!/usr/bin/env node
/**
 * AEGIS-Ω full-stack driver
 * Launches bridge + vite-preview servers, drives them with Playwright, returns exit 0 on success.
 *
 * Usage:
 *   node driver.cjs [--ss]   # --ss: capture screenshots, skip interaction
 *   node driver.cjs --smoke  # smoke test only (no UI, just curl health checks)
 *
 * Ports:  bridge=7890  sovereign-omega=5173  cockpit=5174
 * Screenshots land in /tmp/aegis-screenshots/
 */

'use strict';

const { execSync, spawn } = require('child_process');
const path = require('path');
const fs   = require('fs');
const http = require('http');

const ROOT    = path.resolve(__dirname, '../../..');   // AEGIS-- repo root
const SOV     = path.join(ROOT, 'sovereign-omega-v2');
const COCKPIT = path.join(ROOT, 'cockpit');
const SS_DIR  = '/tmp/aegis-screenshots';
const ARGS    = process.argv.slice(2);
const SMOKE   = ARGS.includes('--smoke');

const PLAYWRIGHT_CORE = '/opt/node22/lib/node_modules/playwright/node_modules/playwright-core';
const CHROMIUM = '/tmp/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell';

// ── helpers ─────────────────────────────────────────────────────────────────

function log(msg) { process.stdout.write(`[aegis-driver] ${msg}\n`); }

function waitHttp(url, timeoutMs = 20000) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeoutMs;
    const attempt = () => {
      http.get(url, res => {
        res.resume();
        if (res.statusCode >= 200 && res.statusCode < 400) return resolve();
        if (Date.now() > deadline) return reject(new Error(`${url} returned ${res.statusCode}`));
        setTimeout(attempt, 500);
      }).on('error', () => {
        if (Date.now() > deadline) return reject(new Error(`${url} unreachable after ${timeoutMs}ms`));
        setTimeout(attempt, 500);
      });
    };
    attempt();
  });
}

function buildIfNeeded(dir, name) {
  const dist = path.join(dir, 'dist', 'index.html');
  if (fs.existsSync(dist)) { log(`${name}: dist/ exists, skipping build`); return; }
  log(`${name}: building...`);
  execSync('npm run build', { cwd: dir, stdio: 'inherit' });
}

function startServer(cmd, args, cwd, label) {
  const proc = spawn(cmd, args, { cwd, stdio: ['ignore','pipe','pipe'], detached: false });
  proc.stdout.on('data', d => process.stdout.write(`  [${label}] ${d}`));
  proc.stderr.on('data', d => process.stderr.write(`  [${label}!] ${d}`));
  proc.on('exit', code => { if (code && code !== 0) log(`${label} exited ${code}`); });
  return proc;
}

// ── main ────────────────────────────────────────────────────────────────────

async function main() {
  const procs = [];

  try {
    // 1. Build both web apps
    buildIfNeeded(SOV,     'sovereign-omega-v2');
    buildIfNeeded(COCKPIT, 'cockpit');

    // 2. Start Python bridge
    log('starting bridge.py on :7890...');
    const bridge = startServer('python', ['python/bridge.py'], SOV, 'bridge');
    procs.push(bridge);
    await waitHttp('http://localhost:7890/health', 25000);
    const health = JSON.parse(execSync('curl -s http://localhost:7890/health').toString());
    log(`bridge health: ${JSON.stringify(health)}`);

    // 3. Start sovereign-omega vite preview
    log('starting sovereign-omega preview on :5173...');
    const sovProc = startServer(
      path.join(SOV, 'node_modules/.bin/vite'),
      ['preview', '--port', '5173', '--host', '0.0.0.0'],
      SOV, 'sov'
    );
    procs.push(sovProc);
    await waitHttp('http://localhost:5173/', 15000);

    // 4. Start cockpit vite preview
    log('starting cockpit preview on :5174...');
    const cockpitProc = startServer(
      path.join(COCKPIT, 'node_modules/.bin/vite'),
      ['preview', '--port', '5174', '--host', '0.0.0.0'],
      COCKPIT, 'cockpit'
    );
    procs.push(cockpitProc);
    await waitHttp('http://localhost:5174/', 15000);

    // 5. Smoke: curl checks
    const telemetry = JSON.parse(execSync('curl -s http://localhost:7890/telemetry').toString());
    const node      = JSON.parse(execSync('curl -s http://localhost:7890/node').toString());
    log(`t0_verdict=${node.t0_verdict}  corruption_count=${node.corruption_count}  pgcs_passes=${telemetry.pgcs_passes}`);
    if (!node.t0_verdict) throw new Error('T0 ABORT: t0_verdict=false');
    if (node.corruption_count !== 0) throw new Error(`CORRUPTION: count=${node.corruption_count}`);
    log('smoke PASS');

    if (SMOKE) { log('--smoke done'); return; }

    // 6. Playwright screenshots + interaction
    fs.mkdirSync(SS_DIR, { recursive: true });
    const { chromium } = require(PLAYWRIGHT_CORE);
    if (!fs.existsSync(CHROMIUM)) throw new Error(`Chromium not found at ${CHROMIUM}\nRun: PLAYWRIGHT_BROWSERS_PATH=/tmp/pw-browsers playwright install chromium`);

    const browser = await chromium.launch({
      executablePath: CHROMIUM,
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    });
    const ctx  = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await ctx.newPage();

    // sovereign-omega
    log('screenshotting sovereign-omega...');
    await page.goto('http://localhost:5173/', { waitUntil: 'domcontentloaded', timeout: 15000 });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${SS_DIR}/sov.png` });
    const sovTitle = await page.title();
    log(`  title: ${sovTitle}`);

    // cockpit
    log('screenshotting cockpit...');
    await page.goto('http://localhost:5174/', { waitUntil: 'domcontentloaded', timeout: 15000 });
    await page.waitForTimeout(3000);
    await page.screenshot({ path: `${SS_DIR}/cockpit.png` });

    // type in cockpit chat
    const textarea = page.locator('textarea').first();
    if (await textarea.count() > 0) {
      await textarea.fill('What is the constitutional hash of this runtime?');
      await page.screenshot({ path: `${SS_DIR}/cockpit-input.png` });
      log(`  typed prompt in cockpit chat`);
    }

    await browser.close();
    log(`screenshots saved to ${SS_DIR}/`);
    log('ALL CHECKS PASS');

  } finally {
    procs.forEach(p => { try { p.kill('SIGTERM'); } catch (_) {} });
  }
}

main().catch(e => { console.error(`FAIL: ${e.message}`); process.exit(1); });
