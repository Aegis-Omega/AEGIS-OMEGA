import json
import math
import httpx
from typing import Dict, Any

class AegisController:
    def __init__(
        self,
        model_url: str,
        model_name: str = "gemma-local",
        uncertainty_max: float = 0.35,
        consistency_min: float = 0.80
    ):
        self.model_url = model_url.rstrip("/")
        self.model_name = model_name
        self.uncertainty_max = uncertainty_max
        self.consistency_min = consistency_min

    def _call_model(self, messages: list) -> str:
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.1
        }
        try:
            with httpx.Client(timeout=httpx.Timeout(60.0, connect=30.0)) as client:
                resp = client.post(f"{self.model_url}/chat/completions", json=payload)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            # Graceful degradation: return structurally valid fallback
            return json.dumps({
                "plan": "CRITICAL_FALLBACK",
                "output": f"Inference pipeline stall intercepted: {str(e)}",
                "tool_calls": []
            })

    def route(self, uncertainty: float) -> str:
        return "LOCAL" if uncertainty <= self.uncertainty_max else "ESCALATE"

    def consistency(self, answer_a: str, answer_b: str) -> float:
        a = set(answer_a.lower().split())
        b = set(answer_b.lower().split())
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    def self_correct(self, task: str, initial_response: str) -> Dict[str, Any]:
        # 1. Critique Phase
        critique_prompt = [
            {"role": "system", "content": "You are a strict constitutional critic. Identify any unsupported claims, schema violations, or logical flaws in the following response."},
            {"role": "user", "content": f"Task: {task}\nResponse: {initial_response}"}
        ]
        critique = self._call_model(critique_prompt)

        # 2. Repair Phase
        repair_prompt = [
            {"role": "system", "content": "You are a proposal engine. Return ONLY valid JSON with keys: 'plan', 'output', 'tool_calls'. Fix all flaws identified by the critic."},
            {"role": "user", "content": f"Task: {task}\nOriginal: {initial_response}\nCritique: {critique}"}
        ]
        repaired = self._call_model(repair_prompt)

        # 3. Consistency Check
        try:
            orig_out = json.loads(initial_response).get("output", "")
            rep_out = json.loads(repaired).get("output", "")
        except json.JSONDecodeError:
            orig_out = initial_response
            rep_out = repaired

        score = self.consistency(orig_out, rep_out)
        accepted = score >= self.consistency_min

        return {
            "original": initial_response,
            "critique": critique,
            "repaired": repaired,
            "consistency": score,
            "accepted": accepted,
            "final_proposal": repaired if accepted else initial_response
        }
