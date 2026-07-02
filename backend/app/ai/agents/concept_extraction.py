from app.ai.provider import get_ai_provider


def run_concept_extraction(payload: dict) -> dict:
    return get_ai_provider().run("concept_extraction", payload)
