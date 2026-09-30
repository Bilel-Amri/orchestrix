"""FastAPI main app.

Endpoints :
  POST /agent/invoke                 - Génère un plan depuis un brief (Lot A)
  POST /agent/approve/{plan_id}      - Approuve un plan (humain)
  POST /ops/execute                  - Exécute un plan approuvé via Ops Agent + ActionGuard (Lot B)
  POST /ops/review/{decision_id}     - Soumet une revue humaine sur une décision REVIEW
  GET  /risk/issues/{issue_key}      - Dernier RiskScore pour une issue (Lot A)
  GET  /risk/alerts                  - Alertes de risque actives
  GET  /audit/recent                 - Dernières entrées du journal d'audit
  GET  /health                       - Healthcheck
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from orchestrix.api.routes import audit_router, ops_router, risk_router, scoping_router
from orchestrix.config import get_settings
from orchestrix.observability.tracing import setup_tracing

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Starting ORCHESTRIX (env=%s, debug=%s)", settings.app_env, settings.app_debug)
    if settings.otel_exporter_otlp_endpoint:
        try:
            setup_tracing()
        except Exception as e:
            logger.warning("OpenTelemetry setup failed (non-fatal): %s", e)
    yield
    logger.info("Shutting down ORCHESTRIX")


app = FastAPI(
    title="ORCHESTRIX",
    description="Copilote multi-agent pour le cadrage, la planification, l'exécution contrôlée et la détection des risques des projets logiciels.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}


# Routers par domaine — le contrat Lot A / Lot B est décrit dans routes.py
app.include_router(scoping_router, prefix="/agent", tags=["Scoping Agent (Lot A)"])
app.include_router(ops_router, prefix="/ops", tags=["Ops Agent + ActionGuard (Lot B)"])
app.include_router(risk_router, prefix="/risk", tags=["Risk Agent (Lot A)"])
app.include_router(audit_router, prefix="/audit", tags=["Audit (Lot B)"])
