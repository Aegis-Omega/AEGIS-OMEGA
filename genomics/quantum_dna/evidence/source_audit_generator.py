"""Bind interpretation corrections to the previously verified QuantumDNA run.

Usage: python build_interpretation_audit.py /path/to/aegis_quantum_dna
Writes audit JSON and Markdown beside this script; never edits the source run.
"""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np

EXPECTED_RECEIPT_SHA256 = 'a04849923bfd9876b9a5aa7aeedd367af81b2ea1ff21d04b4fbd402ebc2f047d'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(root):
    root=Path(root).resolve()
    results=root/'results'
    receipt_path=results/'receipt.json'
    if sha(receipt_path)!=EXPECTED_RECEIPT_SHA256:
        raise ValueError('Source receipt does not match the authorized numerical run')
    receipt=json.loads(receipt_path.read_text())
    count=0
    for folder,key in [(root/'inputs','input_sha256'),(results,'output_sha256')]:
        for name,expected in receipt[key].items():
            path=(folder/name).resolve()
            if not path.is_relative_to(folder.resolve()) or sha(path)!=expected:
                raise ValueError('Artifact binding failure: '+name)
            count+=1
    metrics=json.loads((results/'sweep_metrics.json').read_text())
    observations=[]
    for gamma in [0.,.1,.5]:
        data=np.genfromtxt(results/f'GTG_gamma_{gamma:g}.csv',delimiter=',',skip_header=1)
        row=next(x for x in metrics if x['sequence']=='GTG' and x['gamma_eV']==gamma)
        observations.append({'gamma_eV':gamma,
            'C_l1_at_25_fs':float(data[np.argmin(abs(data[:,0]-25)),7]),
            'C_l1_at_200_fs':float(data[-1,7]),
            'max_C_l1_after_25_fs':float(data[data[:,0]>=25,7].max()),
            'classical_coupling_ratio':row['classical_coupling_ratio'],
            'classical_population_error_after_5_over_Gamma':row['max_population_error_after_transient'],
            'operational_classical_criteria_pass':row['operational_classical_criteria_pass']})
    hamiltonians=[]
    for seq in ['GCG','GTG','GAG','GGG']:
        with np.load(results/f'{seq}_gamma_0_states.npz') as data:
            H=data['H_eV'];rho=data['rho_qdna']
            hamiltonians.append({'sequence':seq,'upper_onsite_eV':H.diagonal()[:3].tolist(),
                'absolute_central_detuning_eV':float(abs(H[1,1]-H[0,0])),
                'H12_eV':float(H[0,1]),'H23_eV':float(H[1,2]),
                'max_interstrand_coupling_eV':float(abs(H[:3,3:]).max()),
                'min_purity_at_gamma_zero':float(np.einsum('tij,tji->t',rho,rho).real.min())})
    X=np.array([[0.,1.],[1.,0.]])
    Z=np.diag([1.,-1.]);Y=np.array([[0.,-1j],[1j,0.]])
    comm=X@Z-Z@X
    real_x=np.array([.6,.8])
    rho_plus=(np.eye(2)+Y)/2;rho_minus=(np.eye(2)-Y)/2
    witness={'real_quadratic_form':float(real_x@comm@real_x),
        'commutator_expectation_plus_imaginary':float(np.trace(rho_plus@comm).imag),
        'minus_i_commutator_expectation_plus':float(np.trace(rho_plus@(-1j*comm)).real),
        'minus_i_commutator_expectation_minus':float(np.trace(rho_minus@(-1j*comm)).real),
        'trace_minus_i_commutator':float(np.trace(-1j*comm).real)}
    audit={
        'schema_version':'AEGIS_QUANTUM_DNA_INTERPRETATION_AUDIT_V1',
        'status':'ARTIFACT_BOUND_INTERPRETATION_AUDIT_ONLY',
        'source_receipt_sha256':EXPECTED_RECEIPT_SHA256,
        'source_code_commit':receipt['code_git_commit'],
        'audit_generator_sha256':sha(__file__),
        'verified_artifact_digest_count':count,
        'reference_replays':receipt['reference_replays'],
        'GTG_coherence_observations':observations,
        'Hamiltonian_observations':hamiltonians,
        'commutator_counterexample':witness,
        'claim_decisions':[
            {'claim':'1BNA published trajectory reproduced by matching Hawke scalar','status':'OVERSTATED',
             'correction':'Separate shipped 1BNA parameter replay from documented Hawke scalar match; external trajectory match remains not established.'},
            {'claim':'GTG C_l1 < 0.2 within 25 fs at gamma=0.1 eV','status':'CONTRADICTED_AT_25_FS',
             'correction':'C_l1(25 fs)=0.21646991105146732; later maximum after25fs=0.22214389871835982.'},
            {'claim':'gamma>=0.1 eV destroys coherence and establishes classical hopping','status':'NOT_ESTABLISHED',
             'correction':'Suppression is measured, not complete destruction; 0.1 and0.5eV fail preregistered asymptotic coupling criterion.'},
            {'claim':'The simulated environment is calibrated thermal noise','status':'NOT_ESTABLISHED',
             'correction':'Pure dephasing is phenomenological; no temperature calibration or thermalizing bath in sweep.'},
            {'claim':'GGG is a trapping state','status':'NOT_ESTABLISHED',
             'correction':'Closed one-hole system has no absorbing trap; G3 population is a finite-time transport diagnostic.'},
            {'claim':'Central base barrier alone explains sequence ranking','status':'UNDERDETERMINED',
             'correction':'Both detuning and coupling matrices change, with lower-strand paths; causal attribution needs controlled ablations.'},
            {'claim':'Complex Hermitian rho alone fixes real positive commutator margin','status':'MATHEMATICALLY_INSUFFICIENT',
             'correction':'[A,B] is anti-Hermitian; -i[A,B] is Hermitian but not uniformly positive over all states in finite dimension.'},
            {'claim':'Riemann-Lebesgue decay annihilates the spectrum','status':'NOT_IMPLIED',
             'correction':'For an L1 Fourier kernel, fixed-parameter transform tends to zero; spectral and uniform-in-parameter conclusions need further assumptions.'},
            {'claim':'Nonzero g_D squared establishes zero exclusion','status':'NOT_IMPLIED',
             'correction':'If g_D is the directional derivative, a nonzero derivative at a zero establishes a transverse zero; notation is undefined without source document.'}
        ],
        'mathematical_document_audit':'NOT_PERFORMED_SECOND_DOCUMENT_NOT_PROVIDED; formula-level reasoning only',
        'control_plane_registration':'NOT_PERFORMED',
        'biological_effect':'HYPOTHESIS_NOT_EXPERIMENTALLY_TESTED',
        'authority_promotion':False}
    out=Path(__file__).resolve().parent
    (out/'AEGIS_QuantumDNA_Interpretation_Audit.json').write_text(json.dumps(audit,indent=2,sort_keys=True,allow_nan=False)+'\n')
    rows='\n'.join(f"| {x['gamma_eV']:g} | {x['C_l1_at_25_fs']:.6f} | {x['C_l1_at_200_fs']:.6f} | {x['operational_classical_criteria_pass']} |" for x in observations)
    hrows='\n'.join(f"| {x['sequence']} | {x['absolute_central_detuning_eV']:.3f} | {x['H12_eV']:.3f} | {x['H23_eV']:.3f} |" for x in hamiltonians)
    report=f'''# AEGIS Ω — audit interpretacije QuantumDNA rezultata

Numerički rezultati ostaju važeći u zadanom modelu. Ovaj audit ispravlja jače interpretacije
i ne dodjeljuje im autoritet fizičkog eksperimenta ili AEGIS Control-Plane prijema.
Ponovo je provjereno {count} otisaka artefakata. Numerički izvorni commit:
`{receipt['code_git_commit']}`. SHA-256 izvornog receipta: `{EXPECTED_RECEIPT_SHA256}`.

## Referentni rezultati

- 1BNA: prvi uzorkovani prelaz preko 1−1/e je 541.0821643286573 fs.
- Hawke2010: 775.5511022044088 fs, poklapanje s dokumentovanim skalarnim rezultatom.
- To su dva odvojena izvora parametara. Hawke skalar ne potvrđuje originalnu 1BNA trajektoriju.
- Referentni proračun traje 3 ps; panel A prikazuje samo prvih 1,5 ps. Prelaz praga nije potpuna rekombinacija.

## Koherencija GTG i klasični komparator

| γ (eV) | C_l1 na 25 fs | C_l1 na 200 fs | Zadani klasični kriterij prolazi |
|---|---:|---:|---|
{rows}

Tvrdnja C_l1 < 0,2 na 25 fs nije tačna za γ=0,1 eV. Koherencija je potisnuta,
ali nije nestala. C_l1 je bezdimenzijska suma modula van-dijagonalnih elemenata u
bazi šest sajtova; njena teorijska gornja granica je 5, pa vrijednost iznad 1 nije
anomalan rezultat niti sama identifikacija Rabi mehanizma. Pri γ=0 model je unitaran;
provjerena čistoća stanja ostaje blizu 1.

Za γ = 0,1/0,5 eV omjer najveće sprege i γ je 0,73/0,146, iznad unaprijed zadane
granice 0,1. Populacijske greške klasičnog komparatora jesu male (oko 0,0194/0,00429),
ali to ne ispunjava sve uslove njegove asimptotske primjenjivosti. Najmanji uzorkovani
GTG uslov koji zadovoljava sve kriterije i sve naredne uzorke je 1 eV. To nije univerzalni γ_c.
Čista dekoherencija ne daje kalibriranu temperaturu, a 1/3 eV su numeričke kontrole.

## Sekvenca: energije i sprege

| Sekvenca | Apsolutni centralni energetski pomak (eV) | H12 (eV) | H23 (eV) |
|---|---:|---:|---:|
{hrows}

GTG ima veći apsolutni centralni energetski pomak od GCG, ali i znatno veću drugu spregu.
Pored gornjeg lanca postoje putevi kroz komplementarni lanac. Slike ne razdvajaju utjecaj
energetskog pomaka, sprega i interferencije; oznaka „timin omogućava tuneliranje” ostaje
mehanistička hipoteza. GGG ima jednake gornje energije u ovom skupu parametara i najveću
prosječnu populaciju G3 u tri tražena uslova, ali nema apsorbirajući trap niti dokazan
mehanizam trajnog hvatanja naboja. Populacije su vremenski prosjeci tokom 0–200 fs.

## Matematičke tvrdnje: ocjena navedenih formula

Drugi dokument nije dostavljen. Nije izvršen audit njegovih definicija, pretpostavki ili dokaza.

1. Za realne simetrične A,B, komutator je antisimetričan i xᵀ[A,B]x=0 za svaki realni x.
   Za kompleksne Hermitske A,B, [A,B] je antihermitski: Tr(ρ[A,B]) je čisto imaginaran.
   Potreban je, na primjer, operator −i[A,B] da očekivanje bude realno. Ni to samo ne daje
   pozitivnu donju među: trag komutatora je 0; uniformna stroga pozitivnost nad svim
   normalizovanim stanjima u konačnoj dimenziji nije moguća. Ograničena klasa stanja
   zahtijeva zaseban dokaz. Pauli primjer u JSON-u daje očekivanja −2 i +2.
2. Riemann–Lebesgue daje nestajanje Fourierove transformacije L1 funkcije za fiksne druge
   parametre. Ne daje automatski uniformnost po σ, nestanak operatorskog spektra ili
   specifičnu stopu opadanja. Ako je A0>0 zamišljen kao donja međa upravo te funkcije na
   cijelom repu, on je s tim limitom nespojiv. Zamjena koraka a0/log(t) sama ne dokazuje
   uniforman spektralni jaz.
3. Ako g_D znači nenulti usmjereni izvod u nuli funkcionala, rezultat je transverzalni
   prolaz kroz postojeću nulu. Primjer Φ(x)=x: Φ(0)=0 i Φ′(0)=1. To nije zero exclusion.
   Sam simbol g_D² nije dovoljno definisan za provjeru izvornog dokumenta.

## Ispravljeni statusi

| Stavka | Status |
|---|---|
| 1BNA | SHIPPED_PARAMETER_REPLAY_VERIFIED; izvorna publikacijska trajektorija nije potvrđena |
| Hawke2010 kontrolni skalar | DOCUMENTED_SCALAR_MATCH |
| Sekvence / koherencija | NUMERICAL_MODEL_RESULTS; potiskivanje koherencije izmjereno u simulaciji |
| Klasični hopping pri 0,1/0,5 eV | OPERATIONAL_CLASSICAL_CRITERIA_NOT_MET |
| Biološki efekat | HYPOTHESIS_NOT_EXPERIMENTALLY_TESTED |
| Drugi matematički dokument | NOT_AUDITED; ocijenjene su samo navedene formule |
| AEGIS Control-Plane registracija | NOT_PERFORMED |

JSON povezuje ove odluke s izvornim receiptom i SHA-256 generatora audita. Izvorni numerički
podaci i historijski receipt nisu izmijenjeni. Ovaj digest zapis nije potpisana attestation.
'''
    (out/'AEGIS_QuantumDNA_Interpretation_Audit.md').write_text(report,encoding='utf-8')
    print('Audit written; verified source digests:',count)
    print('Commutator witness:',witness)


if __name__=='__main__':
    main(sys.argv[1])
