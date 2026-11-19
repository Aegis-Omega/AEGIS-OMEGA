// Read-only, same-origin audit of legal-page delivery. This does not certify legal content.
import { validateOAuthInputs } from './core.mjs';

const FIELDS = Object.freeze(['privacy', 'terms']);

export function analyzeLegalPage({ kind, requestedUrl, finalUrl, status, contentType, body }) {
  if (!FIELDS.includes(kind)) throw new TypeError('Unsupported legal document kind.');
  const fail = (state, reason) => ({ kind, state, reason, documentRouteIdentified: false, legalContentApproved: false });
  if (status !== 200) return fail('UNAVAILABLE', `HTTP ${status}; expected 200.`);
  if (!/\btext\/html\b/i.test(contentType ?? '')) return fail('UNAVAILABLE', 'Response is not HTML.');

  let requested, actual;
  try {
    requested = new URL(requestedUrl);
    actual = new URL(finalUrl);
  } catch {
    return fail('UNAVAILABLE', 'Invalid request or response URL.');
  }
  // Detect redirects to a homepage or a third-party page, both often masquerading as HTTP 200.
  if (requested.origin !== actual.origin || requested.pathname.replace(/\/$/, '') !== actual.pathname.replace(/\/$/, '')) {
    return fail('REDIRECTED', 'The final response does not match the requested legal-page URL.');
  }
  if (typeof body !== 'string' || body.length > 3_000_000) {
    return fail('UNCONFIRMED', 'Missing or oversized response body.');
  }

  // Deterministic marker required to differentiate a legal page from a Vite SPA fallback.
  // The marker is NOT evidence of legal accuracy, approval, or Google ownership.
  const matchingMeta = (body.match(/<meta\b[^>]*>/gi) || []).some(tag => {
    const name = /\bname\s*=\s*(["'])aegis-legal-document\1/i.test(tag);
    const value = new RegExp(`\\bcontent\\s*=\\s*(["'])${kind}\\1`, 'i').test(tag);
    return name && value;
  });
  if (!matchingMeta) {
    return fail('UNCONFIRMED_OR_SPA_FALLBACK', `No page-specific ${kind} marker. A 200 response alone is not proof.`);
  }
  if (!/<main\b/i.test(body)) return fail('UNCONFIRMED', 'Document marker found but no main content element.');
  return {
    kind,
    state: 'DOCUMENT_ROUTE_IDENTIFIED',
    reason: 'Page-specific marker and main element found. Legal accuracy and approval remain OPEN.',
    documentRouteIdentified: true,
    legalContentApproved: false,
  };
}

export async function probeLegalPages({ fields, origin, fetchImpl = globalThis.fetch, timeoutMs = 7000 }) {
  const base = { checkedAt: new Date().toISOString(), googleOwnershipVerified: false, legalContentApproved: false, googleCloudModified: false };
  if (!origin || origin === 'null' || String(origin).startsWith('file:')) {
    return { ...base, state: 'SKIPPED_NON_HTTP_ORIGIN', pages: [], note: 'Run the probe on the canonical HTTPS website.' };
  }
  let normalized;
  try {
    const format = validateOAuthInputs(fields);
    if (format.status !== 'FORMAT_PASS_ONLY') {
      return { ...base, state: 'BLOCKED_INVALID_FORMAT', pages: [], note: 'Fix URL-format errors before probing.' };
    }
    normalized = new URL(origin);
  } catch {
    return { ...base, state: 'BLOCKED_INVALID_FORMAT', pages: [], note: 'Missing or invalid origin/inputs.' };
  }
  if (!['https:', 'http:'].includes(normalized.protocol)) {
    return { ...base, state: 'SKIPPED_NON_HTTP_ORIGIN', pages: [], note: 'Host this file on HTTP(S) to run a same-origin probe.' };
  }
  if (typeof fetchImpl !== 'function') {
    return { ...base, state: 'SKIPPED_FETCH_UNAVAILABLE', pages: [], note: 'Fetch is unavailable in this browser.' };
  }

  const pages = await Promise.all(FIELDS.map(async kind => {
    const url = new URL(fields[kind]);
    if (url.origin !== normalized.origin) {
      return { kind, state: 'SKIPPED_CROSS_ORIGIN', reason: 'Probe never fetches another origin. Run from the actual canonical domain.', documentRouteIdentified: false, legalContentApproved: false };
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const resp = await fetchImpl(url.href, {
        method: 'GET', credentials: 'omit', cache: 'no-store', redirect: 'follow',
        headers: { Accept: 'text/html' }, signal: controller.signal,
      });
      // Bound the read: large/streamed pages are not required to prove legal route identity.
      const contentLength = Number(resp.headers?.get?.('content-length') ?? '0');
      if (contentLength > 3_000_000) {
        return { kind, state: 'UNCONFIRMED', reason: 'Response is too large.', documentRouteIdentified: false, legalContentApproved: false };
      }
      const body = await resp.text();
      return analyzeLegalPage({kind, requestedUrl: url.href, finalUrl: resp.url || url.href,
        status: resp.status, contentType: resp.headers?.get?.('content-type') ?? '', body});
    } catch (error) {
      return { kind, state: 'NETWORK_ERROR', reason: String(error?.name === 'AbortError' ? 'Request timed out.' : (error?.message || error)), documentRouteIdentified: false, legalContentApproved: false };
    } finally {
      clearTimeout(timer);
    }
  }));
  return { ...base, state: pages.every(p => p.documentRouteIdentified) ? 'ROUTES_IDENTIFIED_REVIEW_OPEN' : 'NOT_READY', pages,
    note: 'This checks only same-origin routing and explicit page identity markers, not legal sufficiency, published Google OAuth branding, or Search Console ownership.' };
}
