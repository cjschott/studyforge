from app.ai.provider import get_ai_provider


def run_validation(payload: dict) -> dict:
    return get_ai_provider().run("validation", payload)
