import json
import hashlib
import os
from local_model_client import LocalModelClient
from kernel_one import KernelOneEngine

LOCAL_SYSTEM_PROMPT = """
You are the Proposal Engine inside a constitutional runtime.
Return ONLY valid JSON with this schema:
{
"plan": "string",
"output": "string",
"tool_calls": []
}
Rules:
No extra prose.
No markdown.
Do not mutate state.
Do not reference forbidden files.
Do not expand scope.
"""

class ConstitutionalOrchestratorWithLocalModel:
    def __init__(
        self,
        state_path="state_vector.json",
        db_path="memory_store.sqlite",
        manifest_path="INDEX.yaml",
        local_model_url=None,
        local_model_name=None,
    ):
        self.kernel = KernelOneEngine(manifest_path=manifest_path, db_path=db_path)
        self.local_client = LocalModelClient(
            base_url=local_model_url,
            model=local_model_name,
        )

    def run_local_proposal(self, task: str):
        return self.local_client.generate(
            system_prompt=LOCAL_SYSTEM_PROMPT,
            user_prompt=task,
        )

    def execute_live(self, task: str, mock_metrics: dict):
        try:
            proposal = self.run_local_proposal(task)
        except Exception as e:
            return {
                "status": "RECONCILED_FALLBACK",
                "request_id": hashlib.sha256(task.encode()).hexdigest()[:32],
                "reason": f"Local inference server unavailable: {str(e)}"
            }

        request_payload = {
            "request_id": hashlib.sha256(task.encode()).hexdigest()[:32],
            "task": task,
            "metrics": mock_metrics,
            "parent_witness": None,
            "target_file": None,
        }

        return self.kernel.process_transaction(
            request_payload=request_payload,
            raw_model_response=json.dumps({
                "plan": proposal.plan,
                "output": proposal.output,
                "tool_calls": proposal.tool_calls,
            }),
        )