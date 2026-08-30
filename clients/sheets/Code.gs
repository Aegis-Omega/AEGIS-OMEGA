/**
 * @OnlyCurrentDoc
 * AEGIS-Ω Google Sheets Integration
 * ===================================
 * Connects Google Sheets to the AEGIS-Ω autonomous agent platform.
 * 39 governed agents collaborate on any objective you give them.
 * Results are written as structured reports directly into the sheet.
 *
 * SETUP:
 *   Apps Script → Project Settings → Script Properties → Add:
 *     AEGIS_API_KEY  = your key from aegisomega.com/pricing
 *     AEGIS_BASE_URL = https://aegis-vertex.aegisomega.com  (default)
 */

// ── Menu ──────────────────────────────────────────────────────────────────────

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('⚡ AEGIS-Ω')
    .addItem('Open Agent Control', 'showSidebar')
    .addSeparator()
    .addItem('Platform Status',   'checkStatus')
    .addItem('Setup Guide',       'showSetupModal')
    .addToUi();
}

function showSidebar() {
  const html = HtmlService.createTemplateFromFile('Sidebar')
    .evaluate()
    .setTitle('AEGIS-Ω Control')
    .setXFrameOptionsMode(HtmlService.SandboxMode.IFRAME);
  SpreadsheetApp.getUi().showSidebar(html);
}

// ── Config helpers ────────────────────────────────────────────────────────────

function _getApiKey() {
  return PropertiesService.getScriptProperties().getProperty('AEGIS_API_KEY') || '';
}

function _getBaseUrl() {
  return (
    PropertiesService.getScriptProperties().getProperty('AEGIS_BASE_URL') ||
    'https://aegis-vertex.aegisomega.com'
  );
}

function _fetch(path, method, body) {
  const apiKey = _getApiKey();
  if (!apiKey) return { error: 'AEGIS_API_KEY not set. Go to ⚡ AEGIS-Ω → Setup Guide.' };

  const options = {
    method: method || 'get',
    headers: { 'x-api-key': apiKey, 'content-type': 'application/json' },
    muteHttpExceptions: true,
  };
  if (body) options.payload = JSON.stringify(body);

  let delay = 2000;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const resp = UrlFetchApp.fetch(_getBaseUrl() + path, options);
      const code = resp.getResponseCode();
      if (code === 200) return JSON.parse(resp.getContentText());
      if (code === 429 || code >= 500) { Utilities.sleep(delay); delay *= 2; continue; }
      return { error: 'HTTP ' + code + ': ' + resp.getContentText().slice(0, 200) };
    } catch (e) {
      Utilities.sleep(delay);
      delay *= 2;
      if (attempt === 2) return { error: 'Connection error: ' + e.toString() };
    }
  }
  return { error: 'Timeout — too many retries' };
}

// ── Core: run a full 39-agent collaboration cycle ────────────────────────────

/**
 * Deploy all 39 AEGIS agents on the given objective.
 * @param {string} objective  What the agents should work on.
 * @param {string} mode       'revenue' | 'analysis' | 'gtm' | 'retention'
 * @param {boolean} live      true = real Anthropic API calls; false = fast demo
 * @return {Object}           Full cycle result with artifacts + projection + audit
 */
function runAegisCollaboration(objective, mode, live) {
  return _fetch('/platform/collaborate', 'post', {
    objective: objective || 'Identify our best revenue opportunity',
    mode:      mode  || 'revenue',
    live:      live  || false,
  });
}

// ── Status ────────────────────────────────────────────────────────────────────

/**
 * Returns platform status: version, capabilities, runs remaining.
 */
function getAegisPlatformStatus() {
  return _fetch('/platform/status');
}

function checkStatus() {
  const raw = getAegisPlatformStatus();
  // Bridge wraps success in PlatformEnvelope { data: {...} }; errors are bare { error: ... }
  const s = (raw && raw.data) ? raw.data : raw;
  const usage = (raw && raw.data && raw.data.usage) ? raw.data.usage : null;
  const msg = s.error
    ? '❌ ' + s.error
    : '✅ AEGIS-Ω v' + (s.version || '?') + '\n' +
      'Agents: '    + (s.total_agents || 39) + '\n' +
      'Chain valid: ' + (s.chain_valid ? 'yes' : 'no') +
      (usage ? '\n\nYour account:\n  Tier: ' + usage.tier + '\n  Runs used: ' + usage.usage_count + '/' + usage.usage_limit + '\n  Remaining: ' + usage.remaining_runs : '');
  SpreadsheetApp.getUi().alert('Platform Status', msg, SpreadsheetApp.getUi().ButtonSet.OK);
}

// ── Report writer ─────────────────────────────────────────────────────────────

/**
 * Write a structured AEGIS collaboration report to the active sheet.
 * Creates a new section below the last used row.
 * @param {Object} result  The JSON result from runAegisCollaboration()
 * @return {string}        Human-readable summary of what was written
 */
function writeReportToSheet(result) {
  // Accept both raw result and PlatformEnvelope-wrapped result
  if (result && result.data) result = result.data;
  if (result.error) return 'Error: ' + result.error;

  const sheet    = SpreadsheetApp.getActiveSheet();
  const startRow = Math.max(sheet.getLastRow() + 2, 1);

  // ── Title bar ──
  const titleRange = sheet.getRange(startRow, 1, 1, 7);
  titleRange.merge()
    .setValue('⚡ AEGIS-Ω  ·  ' + (result.cycle_id || 'cycle') +
              '  ·  ' + new Date().toLocaleString())
    .setBackground('#0f172a')
    .setFontColor('#818cf8')
    .setFontWeight('bold')
    .setFontSize(10);

  // ── Summary header ──
  const summaryHdr = ['Objective', 'Mode', 'Departments', 'ARR Projection', 'Tier', 'Verdict', 'Chain'];
  sheet.getRange(startRow + 1, 1, 1, 7)
    .setValues([summaryHdr])
    .setBackground('#1e293b')
    .setFontColor('#94a3b8')
    .setFontWeight('bold')
    .setFontSize(9);

  // ── Summary values ──
  const proj  = result.projection || {};
  const audit = result.constitutional_audit || {};
  const arrFmt = proj.first_year_arr_usd
    ? '$' + Number(proj.first_year_arr_usd).toLocaleString()
    : 'N/A';

  const verdictColor = { APPROVED: '#16a34a', FLAG: '#ca8a04', QUARANTINE: '#dc2626' };
  const verdict      = audit.verdict || 'APPROVED';

  sheet.getRange(startRow + 2, 1, 1, 7).setValues([[
    result.objective                 || '—',
    result.mode                      || 'revenue',
    result.departments_collaborated  || 0,
    arrFmt,
    proj.tier                        || '—',
    verdict,
    result.chain_valid ? '✓' : '✗',
  ]]).setFontSize(9);

  // Colour verdict cell
  sheet.getRange(startRow + 2, 6)
    .setFontColor(verdictColor[verdict] || '#374151')
    .setFontWeight('bold');

  // Governed projection note
  if (proj.governed_note) {
    sheet.getRange(startRow + 3, 1, 1, 7).merge()
      .setValue('📊 ' + proj.governed_note)
      .setFontColor('#6366f1')
      .setFontSize(9)
      .setFontStyle('italic');
  }

  // ── Constitutional concerns (if flagged) ──
  const concerns = audit.concerns || [];
  if (concerns.length > 0) {
    const concernRow = startRow + 4;
    sheet.getRange(concernRow, 1, 1, 7).merge()
      .setValue('⚠️ Constitutional concerns: ' + concerns.slice(0, 3).join(' | '))
      .setBackground('#fef9c3')
      .setFontColor('#92400e')
      .setFontSize(8)
      .setWrap(true);
  }

  // ── Stage outputs ──
  const artifacts = result.artifacts || [];
  const artStart  = startRow + 5 + (concerns.length > 0 ? 1 : 0);

  if (artifacts.length > 0) {
    sheet.getRange(artStart, 1, 1, 7)
      .setValues([['Role', 'Output (first 400 chars)', '', '', '', '', '']])
      .setBackground('#f1f5f9')
      .setFontWeight('bold')
      .setFontSize(9);

    artifacts.forEach(function(art, i) {
      const row = artStart + 1 + i;
      sheet.getRange(row, 1).setValue(art.role || ('stage-' + i)).setFontSize(9).setFontWeight('bold');
      sheet.getRange(row, 2, 1, 6).merge()
        .setValue((art.output || '').slice(0, 400))
        .setWrap(true)
        .setFontSize(8);
    });
  }

  // Auto-resize column A
  sheet.autoResizeColumn(1);

  return (
    'Report written — row ' + startRow +
    ' | ' + artifacts.length + ' agent outputs' +
    (arrFmt !== 'N/A' ? ' | ARR: ' + arrFmt : '')
  );
}

// ── Cell helpers ──────────────────────────────────────────────────────────────

function getActiveCellText() {
  try {
    return SpreadsheetApp.getActiveSheet().getActiveCell().getValue().toString();
  } catch (e) {
    return '';
  }
}

function writeToActiveCell(text) {
  try {
    SpreadsheetApp.getActiveSheet().getActiveCell().setValue(text);
    return 'OK';
  } catch (e) {
    return 'Error: ' + e.message;
  }
}

// ── Setup modal ───────────────────────────────────────────────────────────────

function showSetupModal() {
  const html = HtmlService.createHtmlOutput(
    '<div style="font-family:system-ui,sans-serif;padding:18px;color:#0f172a;line-height:1.6">' +
    '<h3 style="color:#4f46e5;margin:0 0 12px">AEGIS-Ω Setup</h3>' +
    '<ol style="font-size:13px;padding-left:18px">' +
    '<li>In Apps Script, click the gear icon → <b>Project Settings</b>.</li>' +
    '<li>Scroll to <b>Script Properties</b> → <b>Add script property</b>.</li>' +
    '<li>Property name: <code style="background:#f1f5f9;padding:1px 5px;border-radius:3px">AEGIS_API_KEY</code></li>' +
    '<li>Value: paste your AEGIS API key from <b>aegisomega.com/pricing</b>.</li>' +
    '<li>Save, refresh the sheet, and open <b>⚡ AEGIS-Ω → Open Agent Control</b>.</li>' +
    '</ol>' +
    '<p style="font-size:12px;color:#64748b;margin-top:12px">' +
    'Explorer keys (free, 10 runs) are available with no payment.</p>' +
    '</div>'
  ).setWidth(480).setHeight(280);
  SpreadsheetApp.getUi().showModalDialog(html, 'AEGIS-Ω Setup Guide');
}
