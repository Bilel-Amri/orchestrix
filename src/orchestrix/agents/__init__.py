"""ORCHESTRIX — Agents.

Trois agents autonomes (LangGraph state machines) :
  - Scoping Agent   (Lot A) — génère des plans structurés depuis un brief
  - Ops Agent       (Lot B) — traduit un plan approuvé en appels Jira
  - Risk Agent      (Lot A) — surveille l'activité et prédit les risques

⚠️ Le code ci-dessous est un SQUELETTE. Les LLMs sont invoqués via une
   interface stable (LLMClient) — le choix du provider (Ollama / vLLM /
   OpenAI-compatible) se fait via .env.
"""
