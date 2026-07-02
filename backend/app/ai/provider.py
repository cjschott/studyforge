from typing import Any


class DisabledAIProvider:
    name = "disabled"

    def run(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": False,
            "provider": self.name,
            "task": task,
            "message": "AI provider not configured. Configure a provider before running AI-assisted workflows.",
            "data": None,
        }


def get_ai_provider() -> DisabledAIProvider:
    return DisabledAIProvider()
