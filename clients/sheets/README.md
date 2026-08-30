# AEGIS-Ω Google Sheets Integration

Connect any Google Sheet to the AEGIS-Ω autonomous agent platform.
39 governed agents collaborate on your objective and write a structured
report directly into the spreadsheet.

## Setup (3 steps)

**1. Create the script**
- Open your Google Sheet → Extensions → Apps Script
- Replace the default `Code.gs` content with the contents of `Code.gs`
- Add a new HTML file named exactly `Sidebar` and paste `Sidebar.html`
- Save (Ctrl+S)

**2. Add your API key**
- In Apps Script: gear icon → Project Settings → Script Properties
- Add property: `AEGIS_API_KEY` = your key from aegisomega.com/pricing
- (Free Explorer keys: 10 runs, no payment required)

**3. Open the sidebar**
- Refresh your Google Sheet
- Menu bar: ⚡ AEGIS-Ω → Open Agent Control
- Grant permissions on first run

## What the agents report back

Each collaboration cycle writes to your sheet:
- **Cycle ID** + timestamp header
- **Summary row**: departments collaborated, ARR projection, constitutional tier, verdict, chain validity
- **Governed projection note** (T2-tagged engineering hypothesis)
- **Constitutional concerns** (if any violations found)
- **Stage outputs**: one row per agent department (strategy, marketing, sales, etc.)

## Script Properties reference

| Property | Required | Default | Description |
|----------|----------|---------|-------------|
| `AEGIS_API_KEY` | Yes | — | Your AEGIS API key |
| `AEGIS_BASE_URL` | No | `https://aegis-vertex.aegisomega.com` | Custom endpoint |
