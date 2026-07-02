from app.ai.provider import get_ai_provider


def run_source_ingestion(payload: dict) -> dict:
    return get_ai_provider().run("source_ingestion", payload)
