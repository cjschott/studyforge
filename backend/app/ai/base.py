from typing import Any, Protocol


class AIProvider(Protocol):
    name: str

    def run(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...
