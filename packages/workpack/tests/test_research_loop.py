"""Adversarial proof that a cited link or local snapshot is NOT web authentication."""
import copy
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aegis_workpack.research_loop import audit_research
from aegis_workpack.protocol import verify, cli

T = datetime.now(timezone.utc).replace(microsecond=0)
def packet():
    return {
      "schema":"aegis.research-cycle.v1",
      "question":"Which verification workflow improves AEGIS agent reliability?",
      "searches":[{"query":"OpenAI agent traces and independent evaluation","status":"completed","tool":"web"},
                  {"query":"Anthropic evaluator optimizer agent evaluation pattern","status":"completed","tool":"browser"}],
      "sources":[
       {"id":"openai","url":"https://developers.openai.com/api/docs/guides/agent-evals",
        "retrieved_at":T.isoformat(),"artifact":"evidence/openai.txt",
        "sha256":"","excerpt":"Use trace grading and datasets to evaluate agent workflows."},
       {"id":"anthropic","url":"https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents",
        "retrieved_at":T.isoformat(),"artifact":"evidence/anthropic.txt",
        "sha256":"","excerpt":"Agent evaluations need clear criteria and feedback loops."}
      ],
      "comparison":{
        "baseline":"AEGIS currently checks artifact hashes, not the research trail.",
        "alternatives":[
         {"name":"Trace grading first","source_ids":["openai"],
          "advantage":"Can identify concrete step-level problems and tool misuse.",
          "tradeoff":"Requires instrumentation, traces and evaluator maintenance."},
         {"name":"Evaluator optimizer first","source_ids":["anthropic"],
          "advantage":"Independent review can identify gaps before shipping artifacts.",
          "tradeoff":"Costs more inference and depends on reliable assessment criteria."}
        ],"choice":"Trace grading first",
        "reason":"Begin with inspectable runtime facts before subjective evaluator conclusions."
      },
      "evaluation":{
        "metric":"Grounded research packet success rate on independent tasks.",
        "baseline_measure":"No verified grounded research packet rate is available.",
        "target_measure":"Reject all tampered research fixtures across six domains.",
        "falsification_test":"Try forged quote, stale sources, private URLs and one-publisher evidence.",
        "outcome":"NOT_RUN"
      },
      "learning":{
        "observed":"This packet is synthetic and has not proven source authenticity.",
        "next_experiment":"Run independent live source refresh and compare results to archived excerpts.",
        "change_proposed":"Block completion when source hashes or comparison fields are absent."
      }
    }

class ResearchCycleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/"evidence").mkdir()
        self.doc=packet()
        for source in self.doc["sources"]:
            text="NOTE: model-authored summary, not an authenticated page snapshot.\n"+source["excerpt"]+"\n"
            raw=text.encode()
            (self.root/source["artifact"]).write_bytes(raw)
            source["sha256"]=hashlib.sha256(raw).hexdigest()
    def set_evaluation(self, doc, cases=None, outcome="SUPPORTED"):
        cases = cases or [
            {"id":"case01", "expected":"alpha", "baseline":"wrong", "candidate":"alpha"},
            {"id":"case02", "expected":"beta", "baseline":"beta", "candidate":"beta"},
            {"id":"case03", "expected":"gamma", "baseline":"wrong", "candidate":"gamma"}
        ]
        payload = {"schema":"aegis.exact-match-eval.v1", "cases":cases}
        raw = (json.dumps(payload,sort_keys=True)+"\n").encode()
        (self.root/"evidence"/"eval-cases.json").write_bytes(raw)
        doc["evaluation"].update({"metric_kind":"case_exact_match",
                                   "evidence_artifact":"evidence/eval-cases.json",
                                   "evidence_sha256":hashlib.sha256(raw).hexdigest(),
                                   "outcome":outcome})
        return doc

    def audit(self, doc=None):
        return audit_research(self.root,doc if doc is not None else self.doc,now=T)
    def fails(self,doc,expected=None):
        r=self.audit(doc)
        self.assertEqual(r["status"],"BLOCKED",r)
        if expected:self.assertEqual(r["reason"],expected)
    def test_complete_packet_never_attests_web_or_improvement(self):
        r=self.audit()
        self.assertEqual(r["status"],"LOCAL_PACKET_COMPLETE_UNATTESTED")
        self.assertEqual(r["source_authenticity"],"UNVERIFIED")
        self.assertEqual(r["live_web_retrieval"],"NOT_PERFORMED")
        self.assertEqual(r["improvement"],"UNPROVEN")
        self.assertEqual(r["publisher_count"],2)
    def test_no_research(self):
        r=audit_research(self.root,None,now=T)
        self.assertEqual(r["status"],"BLOCKED")
        self.assertEqual(r["reason"],"RESEARCH_SCHEMA_INVALID")
    def test_single_source(self):
        d=copy.deepcopy(self.doc);d["sources"].pop();self.fails(d,"RESEARCH_SOURCES_INSUFFICIENT")
    def test_same_organization_different_subdomain(self):
        d=copy.deepcopy(self.doc)
        d["sources"][1]["url"]="https://docs.openai.com/example"
        d["sources"][0]["url"]="https://developers.openai.com/example"
        self.fails(d,"SOURCE_PUBLISHERS_NOT_INDEPENDENT")
    def test_source_tampering(self):
        (self.root/self.doc["sources"][0]["artifact"]).write_text("fake")
        self.fails(self.doc,"SOURCE_SNAPSHOT_TAMPERED")
    def test_fake_excerpt(self):
        d=copy.deepcopy(self.doc);d["sources"][0]["excerpt"]="What is not in any document is forged";self.fails(d,"SOURCE_EXCERPT_NOT_ANCHORED")
    def test_reject_http(self):
        d=copy.deepcopy(self.doc);d["sources"][0]["url"]="http://example.org";self.fails(d,"SOURCE_URL_UNSAFE")
    def test_reject_local_net_ip(self):
        d=copy.deepcopy(self.doc);d["sources"][0]["url"]="https://127.0.0.1/secret";self.fails(d)
    def test_reject_userinfo(self):
        d=copy.deepcopy(self.doc);d["sources"][0]["url"]="https://evil@site.example.org/path";self.fails(d,"SOURCE_URL_UNSAFE")
    def test_reject_port(self):
        d=copy.deepcopy(self.doc);d["sources"][0]["url"]="https://example.org:12345/path";self.fails(d,"SOURCE_URL_UNSAFE")
    def test_reject_stale_source(self):
        d=copy.deepcopy(self.doc);d["sources"][0]["retrieved_at"]="2026-09-22T00:00:00Z";self.fails(d,"SOURCE_STALE_OR_FUTURE")
    def test_reject_future_source(self):
        d=copy.deepcopy(self.doc);d["sources"][0]["retrieved_at"]="2030-01-01T00:00:00Z";self.fails(d,"SOURCE_STALE_OR_FUTURE")
    def test_reject_naive_source_time(self):
        d=copy.deepcopy(self.doc);d["sources"][0]["retrieved_at"]="2026-10-11T05:00:00";self.fails(d,"RESEARCH_TIME_NAIVE")
    def test_reject_missing_search(self):
        d=copy.deepcopy(self.doc);d["searches"]=[];self.fails(d,"SEARCH_LOG_INVALID")
    def test_reject_unavailable_search(self):
        d=copy.deepcopy(self.doc);d["searches"][0]["status"]="unavailable";self.fails(d,"LIVE_SEARCH_UNRECORDED")
    def test_reject_ungrounded_alternative(self):
        d=copy.deepcopy(self.doc);d["comparison"]["alternatives"][0]["source_ids"]=["fake"];self.fails(d,"ALTERNATIVE_UNGROUNDED")
    def test_reject_one_comparison(self):
        d=copy.deepcopy(self.doc);d["comparison"]["alternatives"].pop();self.fails(d,"COMPARISON_MISSING")
    def test_reject_unselected_choice(self):
        d=copy.deepcopy(self.doc);d["comparison"]["choice"]="Imaginary approach";self.fails(d,"DECISION_NOT_GROUNDED")
    def test_reject_missing_metric(self):
        d=copy.deepcopy(self.doc);d["evaluation"].pop("metric");self.fails(d,"EVALUATION_MISSING")
    def test_reject_missing_falsification(self):
        d=copy.deepcopy(self.doc);d["evaluation"]["falsification_test"]="";self.fails(d,"EVALUATION_MISSING")
    def test_reject_missing_learning(self):
        d=copy.deepcopy(self.doc);d["learning"]["next_experiment"]="";self.fails(d,"LEARNING_MISSING")
    def test_reject_duplicate_source_id(self):
        d=copy.deepcopy(self.doc);d["sources"][1]["id"]="openai";self.fails(d,"SOURCE_ID_DUPLICATE_OR_INVALID")
    def test_path_traversal_source_fails(self):
        d=copy.deepcopy(self.doc);d["sources"][0]["artifact"]="../outside.txt";self.fails(d,"ARTIFACT_PATH_INVALID")
    def test_manifest_research_status_gates_delivery(self):
        raw=b"result";(self.root/"result.txt").write_bytes(raw)
        basic={"schema":"aegis.workpack.v1","task_id":"agent-789","domain":"code","authority":"read_only",
               "objective":"Create a result with source-backed claims","producer":{"agent":"unit"},
               "artifacts":[{"path":"result.txt","sha256":hashlib.sha256(raw).hexdigest()}],
               "checks":[{"id":"A1","kind":"sha256","artifact":"result.txt"}]}
        basic_receipt=verify(self.root,basic)
        self.assertEqual(basic_receipt["artifact_integrity"],"PASS")
        self.assertEqual(basic_receipt["delivery_readiness"],"BLOCKED_RESEARCH_OR_COMPARISON")
        import contextlib,io
        (self.root/"manifest.json").write_text(json.dumps(basic))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli([str(self.root)]),1)
            self.assertEqual(cli([str(self.root),"--integrity-only"]),0)
        basic["research"]=copy.deepcopy(self.doc)
        checked=verify(self.root,basic)
        self.assertEqual(checked["delivery_readiness"],"BLOCKED_UNRUN_FALSIFICATION")
        self.assertEqual(checked["domain_quality"],"UNVERIFIED")
        (self.root/"manifest.json").write_text(json.dumps(basic))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli([str(self.root)]),1)
        basic["research"]["evaluation"]["outcome"]="FALSIFIED"  # forged claim alone
        forged=verify(self.root,basic)
        self.assertEqual(forged["delivery_readiness"],"BLOCKED_RESEARCH_OR_COMPARISON")
        (self.root/"manifest.json").write_text(json.dumps(basic))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli([str(self.root)]),1)
        self.set_evaluation(basic["research"])
        measured=verify(self.root,basic)
        self.assertEqual(measured["delivery_readiness"],"BLOCKED_UNATTESTED_RESEARCH_AND_ORACLE")
        self.assertEqual(measured["local_result"],"LOCAL_INTEGRITY_AND_STRUCTURE_VERIFIED")
        self.assertEqual(measured["disposition"],"NOT_ADMITTED")
        self.assertIs(measured["work_complete"],False)
        (self.root/"manifest.json").write_text(json.dumps(basic))
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            self.assertEqual(cli([str(self.root)]),1)
        self.assertEqual(json.loads(captured.getvalue())["disposition"],"NOT_ADMITTED")
        with contextlib.redirect_stdout(io.StringIO()) as diagnostic:
            self.assertEqual(cli([str(self.root),"--integrity-only"]),0)
        self.assertEqual(json.loads(diagnostic.getvalue())["disposition"],"NOT_ADMITTED")
        self.assertEqual(measured["domain_quality"],"UNVERIFIED")
        self.assertEqual(measured["authority_effect"],"NONE")

    def test_forged_outcome_without_evidence_denied(self):
        d=copy.deepcopy(self.doc);d["evaluation"]["outcome"]="SUPPORTED"
        self.fails(d,"EVALUATOR_KIND_UNSUPPORTED")

    def test_self_authored_oracle_never_completes_work(self):
        import contextlib, io
        d = self.set_evaluation(copy.deepcopy(self.doc), cases=[
            {"id": f"forge{i}", "expected": "claimed_answer",
             "baseline": "different_answer", "candidate": "claimed_answer"}
            for i in range(1, 7)
        ])
        raw = b"result"; (self.root / "result.txt").write_bytes(raw)
        manifest = {"schema":"aegis.workpack.v1", "task_id":"forge-oracle-001",
                    "domain":"science", "authority":"read_only",
                    "objective":"Attempt to pass self-authored benchmark answers",
                    "producer":{"agent":"untrusted-agent"},
                    "artifacts":[{"path":"result.txt","sha256":hashlib.sha256(raw).hexdigest()}],
                    "checks":[{"id":"A1","kind":"sha256","artifact":"result.txt"}],
                    "research":d}
        receipt = verify(self.root,manifest)
        self.assertEqual(receipt["local_result"],"LOCAL_INTEGRITY_AND_STRUCTURE_VERIFIED")
        self.assertEqual(receipt["research"]["evaluation_replay"]["candidate_matches"],6)
        self.assertEqual(receipt["research"]["source_authenticity"],"UNVERIFIED")
        self.assertEqual(receipt["research"]["improvement"],"UNPROVEN")
        self.assertEqual(receipt["disposition"],"NOT_ADMITTED")
        self.assertFalse(receipt["work_complete"])
        self.assertEqual(receipt["delivery_readiness"],"BLOCKED_UNATTESTED_RESEARCH_AND_ORACLE")
        (self.root/"manifest.json").write_text(json.dumps(manifest))
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            status = cli([str(self.root)])
        self.assertEqual(status,1)
        self.assertEqual(json.loads(captured.getvalue())["disposition"],"NOT_ADMITTED")

    def test_explicit_local_diagnostic_never_promotes_work(self):
        import contextlib, io
        raw=b"data";(self.root/"result.txt").write_bytes(raw)
        manifest={"schema":"aegis.workpack.v1", "task_id":"local-only-001",
                  "domain":"data", "authority":"read_only", "objective":"Test explicit local-only diagnostic output",
                  "producer":{"agent":"fixture"},
                  "artifacts":[{"path":"result.txt","sha256":hashlib.sha256(raw).hexdigest()}],
                  "checks":[{"id":"A1","kind":"sha256","artifact":"result.txt"}]}
        (self.root/"manifest.json").write_text(json.dumps(manifest))
        with contextlib.redirect_stdout(io.StringIO()) as c:
            status=cli([str(self.root),"--integrity-only"])
        receipt=json.loads(c.getvalue())
        self.assertEqual(status,0)
        self.assertEqual(receipt["disposition"],"NOT_ADMITTED")
        self.assertFalse(receipt["work_complete"])
        self.assertEqual(receipt["local_result"],"LOCAL_INTEGRITY_AND_STRUCTURE_VERIFIED")

    def test_invalid_contract_still_fails_replay(self):
        raw=b"data";(self.root/"result.txt").write_bytes(raw)
        manifest={"schema":"aegis.workpack.v1", "task_id":"bad-001", "domain":"code",
                  "authority":"root", "objective":"Do not permit unknown authority", "producer":{"agent":"fixture"},
                  "artifacts":[{"path":"result.txt","sha256":hashlib.sha256(raw).hexdigest()}],
                  "checks":[{"id":"A1","kind":"sha256","artifact":"result.txt"}]}
        receipt=verify(self.root,manifest)
        self.assertEqual(receipt["disposition"],"NOT_ADMITTED")
        self.assertEqual(receipt["local_result"],"UNVERIFIED")
        self.assertFalse(receipt["work_complete"])

    def test_computed_improvement_replays(self):
        d=self.set_evaluation(copy.deepcopy(self.doc))
        r=self.audit(d)
        self.assertEqual(r["status"],"LOCAL_PACKET_COMPLETE_UNATTESTED")
        self.assertEqual(r["evaluation_replay"]["baseline_matches"],1)
        self.assertEqual(r["evaluation_replay"]["candidate_matches"],3)
        self.assertEqual(r["evaluation_replay"]["case_count"],3)
        self.assertEqual(r["improvement"],"UNPROVEN")
        self.assertEqual(r["evaluation_replay"]["authenticity"],"UNVERIFIED")

    def test_three_cases_cannot_claim_statistical_signal(self):
        d=self.set_evaluation(copy.deepcopy(self.doc))
        e=self.audit(d)["evaluation_replay"]
        self.assertEqual((e["candidate_improvements"],e["candidate_regressions"]),(2,0))
        self.assertEqual(e["paired_p_value"],0.5)
        self.assertEqual(e["statistical_signal"],"UNDERPOWERED")
        self.assertEqual(e["cross_model_superiority"],"UNPROVEN")

    def test_twenty_discordant_wins_replay_exact_probability(self):
        cases=[{"id":f"case{i:02d}","expected":str(i),"baseline":"wrong",
                "candidate":str(i)} for i in range(20)]
        d=self.set_evaluation(copy.deepcopy(self.doc),cases)
        e=self.audit(d)["evaluation_replay"]
        self.assertEqual(e["statistical_signal"],"POSITIVE_PAIRED_SIGNAL")
        self.assertEqual(e["candidate_improvements"],20)
        self.assertAlmostEqual(e["paired_p_value"],2/(2**20),places=11)
        self.assertEqual(e["oracle_independence"],"UNVERIFIED")

    def test_twenty_discordant_losses_replay_exact_probability(self):
        cases=[{"id":f"case{i:02d}","expected":str(i),"baseline":str(i),
                "candidate":"wrong"} for i in range(20)]
        d=self.set_evaluation(copy.deepcopy(self.doc),cases,outcome="FALSIFIED")
        e=self.audit(d)["evaluation_replay"]
        self.assertEqual(e["statistical_signal"],"NEGATIVE_PAIRED_SIGNAL")
        self.assertEqual(e["candidate_regressions"],20)

    def test_large_sample_small_gain_is_not_significant(self):
        cases=[]
        for i in range(30):
            expected=str(i)
            baseline="wrong" if i < 11 else expected if i < 20 else "wrong"
            candidate=expected if i < 11 else "wrong" if i < 20 else "wrong"
            cases.append({"id":f"case{i:02d}","expected":expected,
                          "baseline":baseline,"candidate":candidate})
        d=self.set_evaluation(copy.deepcopy(self.doc),cases)
        e=self.audit(d)["evaluation_replay"]
        self.assertEqual((e["candidate_improvements"],e["candidate_regressions"]),(11,9))
        self.assertEqual(e["statistical_signal"],"NO_SIGNIFICANT_DIFFERENCE")
        self.assertGreater(e["paired_p_value"],0.05)

    def test_all_ties_have_p_value_one(self):
        cases=[{"id":f"case{i:02d}","expected":str(i),"baseline":str(i),
                "candidate":str(i)} for i in range(20)]
        d=self.set_evaluation(copy.deepcopy(self.doc),cases,outcome="INCONCLUSIVE")
        e=self.audit(d)["evaluation_replay"]
        self.assertEqual(e["paired_p_value"],1.0)
        self.assertEqual(e["discordant_pairs"],0)
        self.assertEqual(e["statistical_signal"],"NO_SIGNIFICANT_DIFFERENCE")

    def test_falsified_self_report_of_supported_denied(self):
        d=self.set_evaluation(copy.deepcopy(self.doc),outcome="FALSIFIED")
        self.fails(d,"EVALUATION_OUTCOME_DISAGREES_WITH_REPLAY")

    def test_evaluation_artifact_tampering_denied(self):
        d=self.set_evaluation(copy.deepcopy(self.doc))
        (self.root/"evidence"/"eval-cases.json").write_text("changed")
        self.fails(d,"EVALUATION_ARTIFACT_TAMPERED")

    def test_duplicate_case_ids_denied(self):
        cases=[{"id":"same1","expected":"a","baseline":"b","candidate":"a"}]*3
        d=self.set_evaluation(copy.deepcopy(self.doc),cases)
        self.fails(d,"EVALUATION_CASE_ID_INVALID_OR_DUPLICATE")

    def test_less_than_three_cases_denied(self):
        cases=[{"id":"only1","expected":"a","baseline":"b","candidate":"a"}]
        d=self.set_evaluation(copy.deepcopy(self.doc),cases)
        self.fails(d,"EVALUATION_CASE_COUNT")

    def test_unsupported_evaluator_denied(self):
        d=self.set_evaluation(copy.deepcopy(self.doc))
        d["evaluation"]["metric_kind"]="arbitrary_python"
        self.fails(d,"EVALUATOR_KIND_UNSUPPORTED")

    def test_wrong_evidence_path_denied(self):
        d=self.set_evaluation(copy.deepcopy(self.doc))
        d["evaluation"]["evidence_artifact"]="../../secrets.txt"
        self.fails(d,"ARTIFACT_PATH_INVALID")

    def test_evaluation_nan_extension_denied(self):
        d=self.set_evaluation(copy.deepcopy(self.doc))
        raw=b'{"schema":"aegis.exact-match-eval.v1","cases":[],"extra":NaN}'
        (self.root / 'evidence' / 'eval-cases.json').write_bytes(raw)
        d['evaluation']['evidence_sha256']=hashlib.sha256(raw).hexdigest()
        self.fails(d, 'NONFINITE_JSON')

    def test_evaluation_float_overflow_denied(self):
        d=self.set_evaluation(copy.deepcopy(self.doc))
        raw=b'{"schema":"aegis.exact-match-eval.v1","cases":[],"extra":1e400}'
        (self.root / 'evidence' / 'eval-cases.json').write_bytes(raw)
        d['evaluation']['evidence_sha256']=hashlib.sha256(raw).hexdigest()
        self.fails(d, 'NONFINITE_JSON')

    def test_invalid_json_dataset_denied(self):
        d=self.set_evaluation(copy.deepcopy(self.doc))
        raw=b'{invalid'
        (self.root/"evidence"/"eval-cases.json").write_bytes(raw)
        d["evaluation"]["evidence_sha256"]=hashlib.sha256(raw).hexdigest()
        self.fails(d,"EVALUATION_ARTIFACT_INVALID_JSON")

    def test_equal_scores_must_be_inconclusive(self):
        cases=[{"id":f"case{i}","expected":str(i),"baseline":str(i),"candidate":str(i)} for i in range(1,4)]
        d=self.set_evaluation(copy.deepcopy(self.doc),cases,outcome="SUPPORTED")
        self.fails(d,"EVALUATION_OUTCOME_DISAGREES_WITH_REPLAY")
        d["evaluation"]["outcome"]="INCONCLUSIVE"
        self.assertEqual(self.audit(d)["evaluation_replay"]["calculated_outcome"],"INCONCLUSIVE")

    def test_candidate_regression_requires_falsified_outcome(self):
        cases=[{"id":f"case{i}","expected":str(i),"baseline":str(i),"candidate":"bad"} for i in range(1,4)]
        d=self.set_evaluation(copy.deepcopy(self.doc),cases,outcome="FALSIFIED")
        self.assertEqual(self.audit(d)["evaluation_replay"]["calculated_outcome"],"FALSIFIED")

    def test_duplicate_dataset_json_key_denied(self):
        d=self.set_evaluation(copy.deepcopy(self.doc))
        raw=b'{"schema":"aegis.exact-match-eval.v1","schema":"aegis.exact-match-eval.v1","cases":[]}'
        (self.root/"evidence"/"eval-cases.json").write_bytes(raw)
        d["evaluation"]["evidence_sha256"]=hashlib.sha256(raw).hexdigest()
        self.fails(d,"DUPLICATE_JSON_KEY")

    @unittest.skipUnless(hasattr(__import__('os'), 'mkfifo'), 'POSIX FIFO only')
    def test_fifo_research_snapshot_never_hangs(self):
        import os, subprocess
        path = self.root / self.doc['sources'][0]['artifact']
        path.unlink()
        os.mkfifo(path)
        import pprint
        script = ("import sys,json;sys.path.insert(0," + repr(str(Path(__file__).resolve().parents[1])) + ");"
                  "from aegis_workpack.research_loop import audit_research;"
                  "print(json.dumps(audit_research("+repr(str(self.root))+","+repr(self.doc)+")))")
        child = subprocess.run([sys.executable, '-S', '-c', script],
                               capture_output=True, text=True, timeout=2)
        self.assertEqual(child.returncode, 0, child.stderr)
        out = json.loads(child.stdout)
        self.assertEqual(out['status'], 'BLOCKED')
        self.assertIn('ARTIFACT_NOT_REGULAR_FILE', out['reason'])

    def test_deep_evaluation_dataset_is_blocked_without_crash(self):
        d=self.set_evaluation(copy.deepcopy(self.doc))
        raw=('{"schema":"aegis.exact-match-eval.v1","cases":['+
             '['*180+'0'+']'*180+']}').encode()
        (self.root/'evidence'/'eval-cases.json').write_bytes(raw)
        d['evaluation']['evidence_sha256']=hashlib.sha256(raw).hexdigest()
        self.fails(d,'JSON_DEPTH_LIMIT')

    def test_huge_integer_evaluation_is_blocked_without_crash(self):
        d=self.set_evaluation(copy.deepcopy(self.doc))
        raw=('{'+'"schema":"aegis.exact-match-eval.v1","cases":['+
             '9'*5000+']}').encode()
        (self.root/'evidence'/'eval-cases.json').write_bytes(raw)
        d['evaluation']['evidence_sha256']=hashlib.sha256(raw).hexdigest()
        self.fails(d,'JSON_INTEGER_TOO_LONG')

if __name__=="__main__": unittest.main()
