// AEGIS OAuth readiness: evidence-based metadata. No Google Cloud writes.
export const REFERENCE = Object.freeze({
  verifiedDate: '2026-11-19',
  source: 'AEGIS Hub source + Vercel project domain read-only check',
  app: 'AEGIS Omega Labs · web hub',
  homepage: 'https://aegisomega.com',
  privacy: 'https://aegisomega.com/privacy',
  terms: 'https://aegisomega.com/terms',
  authorizedDomain: 'aegisomega.com',
  contact: 'info@aegisomega.com',
  evidence: {
    vercelApex: 'VERIFIED_VERCEL_ONLY',
    googleSearchConsole: 'UNKNOWN',
    privacyRouteInMain: 'OPEN_MISSING_ROUTE',
    termsRouteInMain: 'OPEN_MISSING_ROUTE',
    oauthBrandingSavedInGoogle: 'UNKNOWN',
  },
});

const KEYS = ['homepage', 'privacy', 'terms', 'authorizedDomain'];

export function normalizeInputs(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new TypeError('Očekivan je objekt s OAuth poljima.');
  const result = {};
  for (const key of KEYS) {
    if (typeof raw[key] !== 'string' || raw[key].trim().length === 0 || raw[key].length > 2048) {
      throw new TypeError(`Neispravno polje: ${key}`);
    }
    result[key] = raw[key].trim();
  }
  return result;
}

export function validateOAuthInputs(raw) {
  const values = normalizeInputs(raw);
  const checks = [];
  const add = (id, ok, message) => checks.push({ id, status: ok ? 'PASS' : 'FAIL', message });
  let h, p, t;
  for (const field of ['homepage', 'privacy', 'terms']) {
    let u = null;
    try { u = new URL(values[field]); } catch { /* fail closed */ }
    add(`${field}_https`, !!u && u.protocol === 'https:' && !u.username && !u.password && !u.hash, `${field}: HTTPS adresa bez autentifikacijskih podataka i fragmenta`);
    if (field === 'homepage') h = u;
    if (field === 'privacy') p = u;
    if (field === 'terms') t = u;
  }
  const d = values.authorizedDomain.toLowerCase();
  const validDomain = /^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$/.test(d) && d.includes('.') && !d.includes('..');
  add('authorized_domain_format', validDomain, 'Authorized domain: domenska oznaka bez protokola i putanje');
  for (const [field, u] of [['homepage', h], ['privacy', p], ['terms', t]]) {
    const ok = validDomain && !!u && (u.hostname === d || u.hostname.endsWith(`.${d}`));
    add(`${field}_domain`, ok, `${field}: adresa pripada odabranoj domeni ili njenoj poddomeni`);
  }
  add('distinct_documents', !!h && !!p && !!t && h.href !== p.href && h.href !== t.href && p.href !== t.href,
      'Početna, privatnost i uslovi imaju odvojene URL adrese');
  return {
    status: checks.every(x => x.status === 'PASS') ? 'FORMAT_PASS_ONLY' : 'FAIL',
    checks,
    livePagesVerified: false,
    googleOwnershipVerified: false,
    note: 'Provjera formata ne potvrđuje dostupnost stranica, sadržaj pravnih dokumenata niti Google Search Console vlasništvo.',
  };
}
