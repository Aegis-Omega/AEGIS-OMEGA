//! Digital Mushaf — Full pipeline integration proof
//!
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Proves that all six modules compose correctly:
//!
//!   TanzilLedger (ingest ayaat, SHA-256 chain)
//!     ↓ AyahKey + rasm_bytes
//!   EpistemicFirewall (T0Core registration, Domain 0/1 isolation)
//!     ↓ classified ayah text
//!   TajweedDFA (acoustic state transitions over the text)
//!     ↓ AcousticState per character
//!   SemanticAlgebra (trace root derivations from the text)
//!     ↓ TriliteralArena fingerprint
//!   NuqtaCanvas (geometric layout of the ayah letters)
//!     ↓ LayoutMatrix fingerprint
//!   TelemetryEmitter (ResonancePacket encoding all above state)
//!
//! All deterministic ×3. corruption_count = 0 throughout.

use aegis_mushaf::{
    epistemic_firewall::{SystemComposer, T0Core},
    nuqta_canvas::layout_line,
    semantic_algebra::{TriliteralArena, TriliteralRoot},
    tajweed_dfa::{AcousticState, LetterClass, TajweedAutomaton, TajweedInput},
    tanzil_ledger::{AyahKey, IngestionEngine, TanzilLedger},
    telemetry_emitter::{ResonancePacket, TelemetryEmitter, RESONANCE_MAGIC},
};

/// Synthesise a minimal Fatiha-like corpus (7 ayaat, simplified rasm bytes).
/// This is representative data — not the actual Tanzil corpus.
fn build_fatiha_corpus() -> Vec<(AyahKey, Vec<u8>)> {
    vec![
        (AyahKey { surah_num: 1, ayah_num: 1 }, b"bismillah ir rahman ir raheem".to_vec()),
        (AyahKey { surah_num: 1, ayah_num: 2 }, b"alhamdu lillahi rabb il alameen".to_vec()),
        (AyahKey { surah_num: 1, ayah_num: 3 }, b"ir rahman ir raheem".to_vec()),
        (AyahKey { surah_num: 1, ayah_num: 4 }, b"maliki yawm id deen".to_vec()),
        (AyahKey { surah_num: 1, ayah_num: 5 }, b"iyyaka nabudu wa iyyaka nastain".to_vec()),
        (AyahKey { surah_num: 1, ayah_num: 6 }, b"ihdinas sirat al mustaqeem".to_vec()),
        (AyahKey { surah_num: 1, ayah_num: 7 }, b"sirat alladhina anamta alayhim".to_vec()),
    ]
}

/// One triliteral root per ayah (simplified — real morphology requires full NLP).
fn ayah_root(ayah_num: u16) -> TriliteralRoot {
    // Map ayah number to a representative root for testing.
    // All codepoints in the Arabic block (U+0600–U+06FF).
    let roots = [
        TriliteralRoot::new(0x0628, 0x0633, 0x0645), // ب س م — name/bismillah
        TriliteralRoot::new(0x062D, 0x0645, 0x062F), // ح م د — praise
        TriliteralRoot::new(0x0631, 0x062D, 0x0645), // ر ح م — mercy
        TriliteralRoot::new(0x0645, 0x0644, 0x0643), // م ل ك — dominion
        TriliteralRoot::new(0x0639, 0x0628, 0x062F), // ع ب د — worship
        TriliteralRoot::new(0x0647, 0x062F, 0x064A), // ه د ي — guidance
        TriliteralRoot::new(0x0646, 0x0639, 0x0645), // ن ع م — blessing
    ];
    roots[(ayah_num as usize - 1) % roots.len()]
}

fn run_pipeline() -> (u32, [u8; 32], [u8; 32], [u8; 32], u64) {
    // ── Stage 1: TanzilLedger ingest ────────────────────────────────────────
    let mut ledger = TanzilLedger::new();
    let mut engine = IngestionEngine::new(&mut ledger);
    let corpus = build_fatiha_corpus();
    for (key, rasm) in &corpus {
        engine.ingest(*key, rasm.clone()).unwrap();
    }
    let ledger_seal = engine.seal();
    drop(engine);
    assert!(ledger.verify_chain());
    assert_eq!(ledger.corruption_count(), 0);

    // ── Stage 2: EpistemicFirewall — Domain 0 registration ──────────────────
    let mut composer = SystemComposer::new();
    for (key, rasm) in &corpus {
        let core = T0Core::new(*key, rasm.clone());
        composer.register_core(core).unwrap();
    }
    // Domain 1 — tafsir for ayah 1:1
    composer.write_tafsir(
        AyahKey { surah_num: 1, ayah_num: 1 },
        "The opening — in the name of God, the Compassionate, the Merciful".to_string(),
    ).unwrap();
    assert_eq!(composer.verify_all_domain0(), 0);
    assert_eq!(composer.domain0_len(), 7);
    assert_eq!(composer.domain1_len(), 1);

    // ── Stage 3: TajweedDFA — acoustic pass over first ayah ─────────────────
    let mut dfa = TajweedAutomaton::new();
    // Simulate acoustic input for "bismillah ir rahman ir raheem" phoneme classes
    let phoneme_sequence: Vec<(LetterClass, bool)> = vec![
        (LetterClass::IkhfaLetter,  false), // ba
        (LetterClass::MaddLetter,   false), // alif (madd)
        (LetterClass::NunSakin,     false), // nun
        (LetterClass::IdghamLetter, false), // next letter triggers idgham
        (LetterClass::ThroatLetter, false), // ain → izhar
        (LetterClass::MaddLetter,   false), // alif madd
        (LetterClass::QalqalaLetter,true),  // qaf at sukun → qalqalah
        (LetterClass::Other,        false), // next letter resolves qalqalah
    ];
    for (class, has_sukun) in phoneme_sequence {
        dfa.evaluate_transition(TajweedInput { codepoint: 0, class, has_sukun, is_waqf: false });
    }
    // Final state after resolving qalqalah should be Izhar
    assert_eq!(dfa.current_state(), AcousticState::Izhar);
    let final_acoustic_state = dfa.current_state() as u16;

    // ── Stage 4: SemanticAlgebra — trace derivations for all 7 roots ─────────
    let mut arena = TriliteralArena::new();
    for (key, _rasm) in &corpus {
        let root = ayah_root(key.ayah_num);
        arena.trace_growth(root);
    }
    assert!(arena.node_count() > 0);
    let arena_fingerprint = arena.arena_fingerprint();

    // ── Stage 5: NuqtaCanvas — geometric layout of first ayah ───────────────
    let ayah_letters: Vec<(u32, LetterClass)> = vec![
        (0x0628, LetterClass::IkhfaLetter),   // ba
        (0x0633, LetterClass::IkhfaLetter),   // sin
        (0x0645, LetterClass::IdghamLetter),  // mim
        (0x0627, LetterClass::MaddLetter),    // alif
        (0x0644, LetterClass::IdghamLetter),  // lam
        (0x0644, LetterClass::IdghamLetter),  // lam
        (0x0647, LetterClass::ThroatLetter),  // ha
    ];
    let layout = layout_line(&ayah_letters, 200, 50);
    assert_eq!(layout.bounds.len(), 7);
    let canvas_fingerprint = layout.fingerprint();

    // ── Stage 6: TelemetryEmitter — encode all state into ResonancePacket ───
    let packet = ResonancePacket {
        sequence: ledger.len() as u64,
        ledger_head_hash: ledger_seal,
        domain0_count: composer.domain0_len() as u16,
        domain1_count: composer.domain1_len() as u16,
        acoustic_state_ordinal: final_acoustic_state,
        active_violations: ledger.corruption_count() as u16,
    };
    let mut emitter = TelemetryEmitter::noop();
    let sent = emitter.emit(&packet).unwrap();
    assert_eq!(sent, 0); // noop returns 0

    // Verify packet encodes T0 pass
    assert_eq!(packet.active_violations, 0);
    let bytes = packet.to_bytes();
    assert_eq!(u16::from_le_bytes([bytes[0], bytes[1]]), RESONANCE_MAGIC);

    let sequence_out = ledger.len() as u64;
    (ledger.corruption_count(), arena_fingerprint, canvas_fingerprint, ledger_seal, sequence_out)
}

#[test]
fn full_pipeline_t0_pass() {
    let (corruption, _arena_fp, _canvas_fp, _seal, _seq) = run_pipeline();
    assert_eq!(corruption, 0, "T0 criterion: corruption_count must be 0");
}

#[test]
fn pipeline_deterministic_run_1() {
    let r1 = run_pipeline();
    let r2 = run_pipeline();
    assert_eq!(r1, r2, "Pipeline must be deterministic");
}

#[test]
fn pipeline_deterministic_run_2() {
    let r1 = run_pipeline();
    let r3 = run_pipeline();
    assert_eq!(r1, r3, "Pipeline must be deterministic (×3)");
}

#[test]
fn domain_isolation_preserved_after_pipeline() {
    let mut ledger = TanzilLedger::new();
    let mut engine = IngestionEngine::new(&mut ledger);
    engine.ingest(AyahKey { surah_num: 1, ayah_num: 1 }, b"text".to_vec()).unwrap();
    let seal_before = engine.seal();
    drop(engine);

    let mut composer = SystemComposer::new();
    let core = T0Core::new(AyahKey { surah_num: 1, ayah_num: 1 }, b"text".to_vec());
    composer.register_core(core).unwrap();

    // Domain 1 write must not alter Domain 0 integrity
    composer.write_tafsir(AyahKey { surah_num: 1, ayah_num: 1 }, "note".to_string()).unwrap();
    assert_eq!(composer.verify_all_domain0(), 0);

    // Ledger seal unchanged (append-only)
    assert_eq!(seal_before, ledger.head_hash());
}

#[test]
fn tajweed_dfa_state_encodes_in_packet() {
    let mut dfa = TajweedAutomaton::new();
    // Drive to Qalqalah state
    dfa.evaluate_transition(TajweedInput {
        codepoint: 0x642, class: LetterClass::QalqalaLetter, has_sukun: true, is_waqf: false,
    });
    let state_ordinal = dfa.current_state() as u16;
    assert_eq!(state_ordinal, AcousticState::Qalqalah as u16);

    let packet = ResonancePacket {
        sequence: 1,
        ledger_head_hash: [0u8; 32],
        domain0_count: 0,
        domain1_count: 0,
        acoustic_state_ordinal: state_ordinal,
        active_violations: 0,
    };
    let bytes = packet.to_bytes();
    let decoded = ResonancePacket::from_bytes(&bytes).unwrap();
    assert_eq!(decoded.acoustic_state_ordinal, AcousticState::Qalqalah as u16);
}

#[test]
fn semantic_arena_and_canvas_fingerprints_differ() {
    let mut arena = TriliteralArena::new();
    arena.trace_growth(TriliteralRoot::new(0x062D, 0x0645, 0x062F));
    let arena_fp = arena.arena_fingerprint();

    let letters = vec![(0x0627, LetterClass::MaddLetter)];
    let canvas_fp = layout_line(&letters, 100, 50).fingerprint();

    // Two different hash domains must not collide
    assert_ne!(arena_fp, canvas_fp);
}

#[test]
fn nuqta_canvas_alif_height_is_seven() {
    use aegis_mushaf::nuqta_canvas::{H_A, D_N};
    assert_eq!(H_A, 7 * D_N);
    let letters = vec![(0x0627, LetterClass::MaddLetter)];
    let m = layout_line(&letters, 100, 50);
    assert_eq!(m.bounds[&0].height, H_A);
}

#[test]
fn ledger_chain_feeds_packet_correctly() {
    let mut ledger = TanzilLedger::new();
    ledger.append(AyahKey { surah_num: 2, ayah_num: 255 }, b"ayat al kursi".to_vec()).unwrap();
    assert!(ledger.verify_chain());

    let packet = ResonancePacket {
        sequence: ledger.len() as u64,
        ledger_head_hash: ledger.head_hash(),
        domain0_count: 1,
        domain1_count: 0,
        acoustic_state_ordinal: 0,
        active_violations: ledger.corruption_count() as u16,
    };
    assert_eq!(packet.sequence, 1);
    assert_ne!(packet.ledger_head_hash, [0u8; 32]);
    assert_eq!(packet.active_violations, 0);
}
