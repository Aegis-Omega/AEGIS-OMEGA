import json
from pathlib import Path
from kernel_one import KernelOneEngine

PAYLOADS = Path("adversarial_payloads.jsonl")

def load_payloads():
    items = []
    for line in PAYLOADS.read_text().splitlines():
        if line.strip():
            items.append(json.loads(line))
    return items

def main():
    kernel = KernelOneEngine()
    cases = load_payloads()
    passed_assertions = 0
    print(f"[TEST RUNNER] Executing {len(cases)} Test Manifest Configurations...\n")

    for case in cases:
        request = {
            "request_id": case.get("request_id", "UNKNOWN"),
            "task": case.get("task", ""),
            "metrics": case.get("metrics", {}),
            "parent_witness": None,
            "target_file": case.get("target_file")
        }

        proposal_dict = {}
        if "plan" in case or "output" in case or "tool_calls" in case:
            if "plan" in case:
                proposal_dict["plan"] = case["plan"]
            if "output" in case:
                proposal_dict["output"] = case["output"]
            if "tool_calls" in case:
                proposal_dict["tool_calls"] = case["tool_calls"]
        else:
            if case.get("name") != "missing_tool_calls":
                proposal_dict = {
                    "plan": "Default valid action blueprint strategy",
                    "output": "Execution block finalized cleanly.",
                    "tool_calls": []
                }
            else:
                proposal_dict = {
                    "plan": "Implement orchestrator",
                    "output": "done"
                }

        if "unexpected" in case:
            proposal_dict["unexpected"] = case["unexpected"]

        raw_model_response = json.dumps(proposal_dict)
        result = kernel.process_transaction(request, raw_model_response)

        status_match = result["status"] == case["expected_status"]
        if status_match:
            passed_assertions += 1
            status_symbol = "[OK]"
        else:
            status_symbol = "[FAIL]"

        print(f"{status_symbol} {case['name']:<30} => Returned: {result['status']:<20} | Expected: {case['expected_status']}")
        if not status_match:
            print(f"       Reason Noted: {result.get('reason')}")

    print(f"\n[METRICS] Verification finished. Passed: {passed_assertions}/{len(cases)} assertions.")
    if passed_assertions != len(cases):
        raise SystemExit("Security Gate Core Failure: Adversarial bypass detected.")

if __name__ == "__main__":
    main()