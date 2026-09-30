"""Streamlit dashboard — squelette à compléter.

Pages à implémenter :
  1. Plans en attente de validation humaine (file d'attente)
  2. Risk alerts actives
  3. Comparaison d'ablations A→E (RQ1)
  4. Métriques de modèles (Effort / Priority / Risk)
  5. Audit log récent
  6. Performance : latence p50/p95, coût par tâche, fallback rate

Lancer avec :
  streamlit run src/orchestrix/dashboard/app.py
"""
import streamlit as st

st.set_page_config(
    page_title="ORCHESTRIX · Dashboard",
    page_icon="🛡️",
    layout="wide",
)

st.title("🛡️ ORCHESTRIX")
st.markdown("### Production Platform for Reliable AI Agents")

st.info(
    "👋 Dashboard en construction.\n\n"
    "Pages prévues :\n"
    "  - Plans en attente de validation\n"
    "  - Risk alerts actives\n"
    "  - Ablations A→E\n"
    "  - Métriques modèles\n"
    "  - Audit log\n"
    "  - Performance / coûts"
)

# TODO: connecter aux vraies sources
# - MLflow tracking URI pour les métriques
# - PostgreSQL audit_log pour les actions récentes
# - Redis pour la file de validation humaine
