# AEGIS Omega Control Browser Extension

Manifest V3 extension for Chrome and Microsoft Edge.

## Install
Chrome: `chrome://extensions` → Developer mode → Load unpacked.
Edge: `edge://extensions` → Developer mode → Load unpacked.

Select the extracted `aegis-omega-browser-extension` folder.

## Capabilities
- Opens OpenAI, GitHub, Cloudflare, Azure AI, ChatGPT, and AEGIS.
- Checks configured MCP/API health endpoints.
- Stores endpoint URLs only.
- Copies task text locally.

## Security boundary
No API keys, passwords, cookies, app passwords, or tokens are stored. The extension performs no privileged writes. Add future write features only through OAuth and AEGIS authority receipts.

## Permission audit (2026-07-26)

v0.1.0 requested more than this README claimed. Corrected in v0.1.1.

| Removed | Why it was not needed |
|---------|----------------------|
| `"tabs"` | `chrome.tabs.create({url})` requires no permission. `"tabs"` grants read access to the URL, title and favicon of **every open tab**. |
| `https://github.com/*` | Only opened in a tab. Host permission would allow requests to the origin from the extension context, against the logged-in session. |
| `https://dash.cloudflare.com/*` | same |
| `https://ai.azure.com/*` | same |
| `https://platform.openai.com/*` | same |
| `https://aegisomega.com/*` | same |

Retained: `storage`, plus host permissions for the two health endpoints the
popup actually `fetch`es.

**Rule this enforces.** A store reviewer reads `manifest.json`, not this file.
Granted capability must not exceed declared capability — the same claim/binding
agreement the rest of AEGIS requires. A URL configured in Options outside the
two retained origins now fails closed instead of being fetched.
