from app.ai.provider import get_ai_provider


def test_default_ai_provider_is_disabled_with_clear_message():
    provider = get_ai_provider()

    result = provider.run("source_ingestion", {"text": "sample"})

    assert result["ok"] is False
    assert "AI provider not configured" in result["message"]
