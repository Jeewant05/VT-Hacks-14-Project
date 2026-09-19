from fastapi.testclient import TestClient

from server.app.config import Settings
from server.app.main import create_app
from server.app.providers import OpenAICompatibleProvider, build_provider


def test_huggingface_provider_uses_shared_token_and_role_model():
    settings = Settings(
        hf_token="hf-test",
        huggingface_model="openai/gpt-oss-120b:fastest",
        huggingface_model_backend="Qwen/backend-coder:fastest",
    )

    provider = build_provider("huggingface", settings, "backend")

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.name == "huggingface"
    assert provider.api_key == "hf-test"
    assert provider.model == "Qwen/backend-coder:fastest"
    assert provider.base_url == "https://router.huggingface.co/v1"


def test_live_config_exposes_three_huggingface_agents(tmp_path):
    settings = Settings(
        database_path=tmp_path / "state.db",
        backend_provider="huggingface",
        frontend_provider="huggingface",
        qa_provider="huggingface",
        hf_token="hf-test",
        huggingface_model_backend="model/backend:fastest",
        huggingface_model_frontend="model/frontend:fastest",
        huggingface_model_qa="model/integration:fastest",
    )
    client = TestClient(create_app(settings))

    result = client.get("/api/live/config")

    assert result.status_code == 200
    body = result.json()
    assert body["configured"] is True
    assert [role["provider"] for role in body["roles"]] == [
        "huggingface",
        "huggingface",
        "huggingface",
    ]
    assert [role["model"] for role in body["roles"]] == [
        "model/backend:fastest",
        "model/frontend:fastest",
        "model/integration:fastest",
    ]
