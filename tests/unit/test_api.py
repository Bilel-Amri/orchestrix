"""Tests unitaires de l'API FastAPI — contrat Lot A / Lot B (Semaine 2).

Sans DB, sans LLM, sans réseau :
  - 422 si le body /agent/invoke est invalide (validation Pydantic)
  - 501 tant que ScopingAgent.generate_plan n'est pas implémenté (Lot A)
  - 503 si les dépendances lourdes du ScopingAgent sont absentes
  - 501 sur les routes /ops, /risk, /audit (stubs Semaine 1)
  - routers bien montés sur leurs prefixes
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from orchestrix.api.main import app


@pytest.fixture(scope="module")
def client():
    # raise_server_exceptions=False : on veut tester les réponses d'erreur HTTP,
    # pas faire remonter l'exception brute dans le client de test.
    return TestClient(app, raise_server_exceptions=False)


class TestHealth:
    def test_health_ok(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json() == {"status": "ok", "version": "0.1.0"}


class TestInvokeContract:
    def test_invoke_valid_body_returns_501(self, client, sample_brief):
        res = client.post("/agent/invoke", json={"brief": sample_brief})
        assert res.status_code in (501, 503)

    def test_invoke_invalid_body_returns_422(self, client):
        res = client.post("/agent/invoke", json={"brief": "trop court"})
        assert res.status_code == 422

    def test_invoke_missing_body_returns_422(self, client):
        res = client.post("/agent/invoke", json={})
        assert res.status_code == 422

    def test_invoke_rejects_non_json(self, client):
        res = client.post(
            "/agent/invoke", content=b"not json", headers={"Content-Type": "application/json"}
        )
        assert res.status_code == 422


class TestRoutersMounted:
    def test_agent_prefix(self, client, sample_brief):
        res = client.post("/agent/invoke", json={"brief": sample_brief})
        assert res.status_code != 404

    def test_ops_prefix(self, client):
        res = client.post("/ops/execute?plan_id=00000000-0000-0000-0000-000000000000")
        assert res.status_code != 404

    def test_risk_prefix(self, client):
        res = client.get("/risk/alerts")
        assert res.status_code != 404

    def test_audit_prefix(self, client):
        res = client.get("/audit/recent")
        assert res.status_code != 404
