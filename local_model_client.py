from __future__ import annotations
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List
import httpx

@dataclass
class LocalModelResponse:
    plan: str
    output: str
    tool_calls: List[Dict[str, Any]]
    raw: Dict[str, Any]

class LocalModelClient:
    def __init__(
        self,
        base_url: str = None,
        model: str = None,
        timeout: float = 60.0,
    ):
        self.base_url = (base_url or os.getenv("AEGIS_MODEL_URL", "http://127.0.0.1:8080/v1")).rstrip("/")
        self.model = model or os.getenv("AEGIS_MODEL_NAME", "gemma-local")
        self.timeout = timeout

    def generate(self, system_prompt: str, user_prompt: str) -> LocalModelResponse:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }

        url = f"{self.base_url}/chat/completions"

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        parsed = self._parse_json_object(content)

        return LocalModelResponse(
            plan=parsed.get("plan", ""),
            output=parsed.get("output", ""),
            tool_calls=parsed.get("tool_calls", []),
            raw=data,
        )

    def _parse_json_object(self, text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise ValueError("Local model did not return a valid JSON object.")
            return json.loads(text[start : end + 1])