import json
from pathlib import Path
from kernel_one import KernelOneEngine

PAYLOADS = Path("adversarial_payloads.jsonl")

def load_payloads():
    return [json.loads(line) for line in PAYLOADS.read_text().splitlines() if line.strip()]

def main():
    kernel = KernelOneEngine()
    cases = load_payloads()
    passed_assertions = 0
    print(f"[TEST RUNNER] Executing {len(cases)} Test Manifest Configurations...\n")

    for case in cases:
        request = {"task": case.get("task", ""), "metrics": case.get("metrics", {}), "parent_witness": None}
        if "request_id" in case: request["request_id"] = case["request_id"]
        if "target_file" in case: request["target_file"] = case["target_file"]

        proposal_dict = {}
        if "plan" in case or "output" in case or "tool_calls" in case:
            if "plan" in case: proposal_dict["plan"] = case["plan"]
            if "output" in case: proposal_dict["output"] = case["output"]
            if "tool_calls" in case: proposal_dict["tool_calls"] = case["tool_calls"]
        else:
            proposal_dict = {"plan": "Default valid action blueprint strategy", "output": "Execution block finalized cleanly.", "tool_calls": []} if case.get("name") != "missing_tool_calls" else {"plan": "Implement orchestrator", "output": "done"}
        
        if "unexpected" in case: proposal_dict["unexpected"] = case["unexpected"]

        result = kernel.process_transaction(request, json.dumps(proposal_dict))
        status_match = result["status"] == case["expected_status"]
        
        if status_match:
            passed_assertions += 1
            print(f"[OK] {case['name']:<30} => Returned: {result['status']:<20} | Expected: {case['expected_status']}")
        else:
            print(f"[FAIL] {case['name']:<30} => Returned: {result['status']:<20} | Expected: {case['expected_status']}")
            print(f"       Reason Noted: {result.get('reason')}")

    print(f"\n[METRICS] Verification finished. Passed: {passed_assertions}/{len(cases)} assertions.")
    if passed_assertions != len(cases):
        raise SystemExit("Security Gate Core Failure: Adversarial bypass detected.")

if __name__ == "__main__":
    main()
