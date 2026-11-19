import { REFERENCE, validateOAuthInputs, normalizeInputs } from './core.mjs';
import { probeLegalPages } from './page-probe.mjs';
const values = {homepage:REFERENCE.homepage,privacy:REFERENCE.privacy,terms:REFERENCE.terms,authorizedDomain:REFERENCE.authorizedDomain};
const selectors = Object.fromEntries(Object.keys(values).map(k => [k, document.querySelector(`#field-${k}`)]));
const live = document.querySelector('#live-region');
const results = document.querySelector('#results');
const webmcpStatus = document.querySelector('#webmcp-status');
const probeReport = document.querySelector('#probe-report');
const probeButton = document.querySelector('#probe-pages');
let probeGeneration = 0;

function setMessage(value) { live.textContent = value; }
function current() { return Object.fromEntries(Object.entries(selectors).map(([k, el])=>[k, el.value])); }
function stage(input) {
  const parsed = normalizeInputs(input);
  for (const [key, val] of Object.entries(parsed)) selectors[key].value = val;
  invalidateProbe();
  renderChecks();
  return { stagedLocally: true, googleCloudModified: false, fields: parsed };
}
function renderChecks() {
  try {
    const result = validateOAuthInputs(current());
    results.replaceChildren(...result.checks.map(check => {
      const li = document.createElement('li');
      li.className = `check ${check.status === 'PASS' ? 'pass' : 'fail'}`;
      const flag = document.createElement('span'); flag.textContent = check.status;
      const copy = document.createElement('span'); copy.textContent = check.message;
      li.append(flag, copy);
      return li;
    }));
    document.querySelector('#check-count').textContent = `${result.checks.filter(x=>x.status==='PASS').length}/${result.checks.length}`;
    setMessage(result.status === 'FORMAT_PASS_ONLY'
      ? 'Format je valjan. Pravne stranice i vlasništvo u Googleu ostaju OPEN/UNKNOWN.'
      : 'Postoje greške u formatu konfiguracije.');
    return result;
  } catch (error) {
    setMessage(`Neuspjela provjera: ${String(error.message || error)}`);
    results.replaceChildren();
    return {status:'FAIL', error:String(error.message || error)};
  }
}
function invalidateProbe() {
  probeGeneration += 1;
  probeReport.textContent = 'Provjera pravnih ruta još nije pokrenuta za ove vrijednosti.';
}

async function runPageProbe() {
  const generation = ++probeGeneration;
  probeButton.disabled = true;
  probeReport.textContent = 'Provjeravam javne dokumente na ovoj domeni…';
  try {
    const check = await probeLegalPages({ fields: current(), origin: window.location.origin });
    if (generation !== probeGeneration) return { ...check, ignoredStaleResult: true };
    const list = document.createElement('ul');
    list.className = 'probe-list';
    for (const page of check.pages) {
      const row = document.createElement('li');
      const state = document.createElement('strong');
      state.textContent = `${page.kind.toUpperCase()}: ${page.state}`;
      const reason = document.createElement('span');
      reason.textContent = page.reason;
      row.append(state, reason);
      list.append(row);
    }
    probeReport.replaceChildren();
    const status = document.createElement('p');
    status.textContent = `Ishod provjere: ${check.state}. ${check.note}`;
    probeReport.append(status, list);
    setMessage('Provjera ruta je završena. Sadržaj pravnih dokumenata i Google verifikacija nisu potvrđeni.');
    return check;
  } catch(error) {
    const message = String(error?.message || error);
    if (generation === probeGeneration) probeReport.textContent = `Greška provjere: ${message}`;
    return { state:'ERROR', error: message, googleCloudModified:false };
  } finally {
    probeButton.disabled = false;
  }
}

for(const el of Object.values(selectors)) el.addEventListener('input', () => { invalidateProbe(); renderChecks(); });
probeButton.addEventListener('click', runPageProbe);
for(const button of document.querySelectorAll('[data-copy]')) {
  button.addEventListener('click', async () => {
    const key = button.dataset.copy;
    const val = selectors[key]?.value;
    if (!val) return;
    try {
      if(!navigator.clipboard?.writeText) throw new Error('Clipboard API nedostupan');
      await navigator.clipboard.writeText(val);
      setMessage(`Kopirano: ${key}`);
    } catch {
      selectors[key].focus(); selectors[key].select();
      setMessage('Automatsko kopiranje nije dozvoljeno. Vrijednost je označena za ručno kopiranje.');
    }
  });
}
document.querySelector('#run-checks').addEventListener('click', renderChecks);
document.querySelector('#reset-fields').addEventListener('click', () => { stage(values); setMessage('Vraćene su izvorne vrijednosti. Google Cloud nije izmijenjen.'); });

// Imperative WebMCP: page-scoped, feature-detected, no outside writes.
function registerWebMCP() {
  const context = document.modelContext;
  if (!context?.registerTool) {
    webmcpStatus.textContent = 'Browser nema WebMCP podršku; UI ostaje potpuno upotrebljiv.';
    return;
  }
  const controller = new AbortController();
  window.addEventListener('pagehide', () => controller.abort(), {once:true});
  const tools = [
    {
      name:'get_aegis_oauth_branding', title:'Read AEGIS OAuth branding fields',
      description:'Read staged AEGIS OAuth URL fields and verified versus open evidence. Does not access Google Cloud.',
      inputSchema:{type:'object',properties:{},additionalProperties:false},
      annotations:{readOnlyHint:true,untrustedContentHint:false},
      execute(){ return {fields:current(),evidence:REFERENCE.evidence,googleCloudModified:false}; },
    },
    {
      name:'validate_aegis_oauth_branding', title:'Validate AEGIS OAuth URL formats',
      description:'Run local HTTPS and authorized-domain format checks. Does not test legal-page availability or Search Console verification.',
      inputSchema:{type:'object',properties:{},additionalProperties:false},
      annotations:{readOnlyHint:true,untrustedContentHint:false},
      execute(){return validateOAuthInputs(current());},
    },
    {
      name:'probe_aegis_oauth_pages', title:'Check AEGIS legal page routing',
      description:'Perform GET requests only to this website origin for the current privacy and terms URLs, detect missing pages and SPA fallback. Does not certify legal documents or change Google Cloud.',
      inputSchema:{type:'object',properties:{},additionalProperties:false},
      annotations:{readOnlyHint:true,untrustedContentHint:false},
      execute(){return runPageProbe();},
    },
    {
      name:'stage_aegis_oauth_branding', title:'Stage OAuth fields in AEGIS readiness page',
      description:'Populate visible local form only. Never edits the Google OAuth consent screen or any deployment.',
      inputSchema:{type:'object',properties:{
        homepage:{type:'string'},privacy:{type:'string'},terms:{type:'string'},authorizedDomain:{type:'string'}
      },required:['homepage','privacy','terms','authorizedDomain'],additionalProperties:false},
      annotations:{readOnlyHint:false,untrustedContentHint:false},
      execute(input) {const result=stage(input);setMessage('Polja su ažurirana samo na ovoj stranici.');return result;},
    },
  ];
  Promise.allSettled(tools.map(tool=>Promise.resolve().then(()=>context.registerTool(tool,{signal:controller.signal})))).then(results=>{
    const count=results.filter(x=>x.status==='fulfilled').length;
    webmcpStatus.textContent = `${count}/${tools.length} WebMCP alata registrovano u ovoj stranici.`;
  }).catch(error=>{webmcpStatus.textContent=`Registracija nije uspjela: ${error?.message||error}`;});
}
renderChecks();
registerWebMCP();
