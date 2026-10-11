#!/usr/bin/env python3
"""Create a local comparative research example, with UNATTESTED source notes.

This generator does NOT visit these websites. The cited links were inspected
separately in the development session; notes are NOT copies of source pages.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from aegis_workpack.protocol import verify

ROOT=Path(__file__).parent/"examples"/"data-research"
(ROOT/"evidence").mkdir(parents=True,exist_ok=True)
now=datetime.now(timezone.utc).replace(microsecond=0).isoformat()
sources=[
 {"id":"openai","url":"https://developers.openai.com/api/docs/guides/agent-evals",
  "excerpt":"OpenAI documentation describes trace grading, datasets and evaluators for agent workflows.",
  "artifact":"evidence/openai-notes.txt"},
 {"id":"anthropic","url":"https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents",
  "excerpt":"Anthropic discusses designing agent evaluations to find failures before production.",
  "artifact":"evidence/anthropic-notes.txt"}
]
for source in sources:
    text=("MODEL-AUTHORED DEVELOPMENT NOTES — NOT VERIFIED HTML / NOT PROOF OF VISIT\n"
          +source["excerpt"]+"\n")
    encoded=text.encode()
    (ROOT/source["artifact"]).write_bytes(encoded)
    source["sha256"]=hashlib.sha256(encoded).hexdigest()
    source["retrieved_at"]=now

data=b"id,accuracy\n1,0.7\n2,0.8\n"
(ROOT/"sample.csv").write_bytes(data)
manifest={
 "schema":"aegis.workpack.v1","task_id":"public-research-demo-001","domain":"data",
 "authority":"read_only","objective":"Demonstrate bounded comparative research and local data integrity",
 "producer":{"agent":"synthetic-fixture-not-independent-agent"},
 "artifacts":[{"path":"sample.csv","sha256":hashlib.sha256(data).hexdigest()}],
 "checks":[{"id":"A1","kind":"sha256","artifact":"sample.csv"},
           {"id":"A2","kind":"csv_columns","artifact":"sample.csv","columns":["id","accuracy"],"min_rows":2}],
 "research":{
  "schema":"aegis.research-cycle.v1",
  "question":"Which agent evaluation approach should AEGIS prototype next?",
  "searches":[{"query":"OpenAI agent evaluation traces and graders","tool":"web","status":"completed"},
              {"query":"Anthropic evaluating autonomous agents production","tool":"web","status":"completed"}],
  "sources":sources,
  "comparison":{
   "baseline":"AEGIS WorkPack currently verifies artifact integrity but not real agent usefulness.",
   "alternatives":[
    {"name":"Trace-grading harness","source_ids":["openai"],
     "advantage":"Captures tool calls and handoffs for failure attribution.",
     "tradeoff":"Requires event instrumentation and evaluator calibration."},
    {"name":"Evaluator optimizer loop","source_ids":["anthropic"],
     "advantage":"Supports explicit feedback to iteratively improve agent outputs.",
     "tradeoff":"Can amplify evaluator errors and adds compute expense."}],
   "choice":"Trace-grading harness",
   "reason":"A low-cost, read-only trace baseline should precede closed-loop optimization."},
  "evaluation":{
   "metric":"Percentage of independent task failures correctly identified before admission.",
   "baseline_measure":"UNKNOWN: no real-work baseline has been measured in this fixture.",
   "target_measure":"At least 90 percent coverage on a held-out multi-domain task set.",
   "falsification_test":"Try 20 real tasks with known failure modes and adversarial source contamination.",
   "outcome":"NOT_RUN"},
  "learning":{
   "observed":"Only research note bytes and manifest structure were checked offline.",
   "next_experiment":"Independently retrieve both live sources and run held-out failures with calibrated graders.",
   "change_proposed":"Start trace-based evaluation without adding runtime or production authority."}
 }
}
(ROOT/"manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
report=verify(ROOT,manifest)
(ROOT/"receipt.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
assert report["delivery_readiness"]=="BLOCKED_UNRUN_FALSIFICATION",report
assert report["research"]["source_authenticity"]=="UNVERIFIED"
assert report["domain_quality"]=="UNVERIFIED"
print("research packet structurally complete; experiment NOT_RUN; delivery BLOCKED; sources UNVERIFIED")
