from app.ai.provider import get_ai_provider


def run_question_generation(payload: dict) -> dict:
    return get_ai_provider().run("question_generation", payload)
