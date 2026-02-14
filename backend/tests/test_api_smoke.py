from fastapi.testclient import TestClient

from app.db import engine
from app.main import app
from app.models import Base


def test_health_endpoint_smoke() -> None:
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as client:
        response = client.get('/api/health')

    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ok'
    assert payload['llm_provider'] == 'openai'
