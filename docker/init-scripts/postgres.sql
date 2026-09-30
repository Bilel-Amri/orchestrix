-- =====================================================================
-- ORCHESTRIX — Initialisation PostgreSQL + extensions
-- Ce script est exécuté au premier démarrage du conteneur postgres.
-- =====================================================================

-- Activer pgvector (recherche vectorielle pour RAG)
CREATE EXTENSION IF NOT EXISTS vector;

-- Activer uuid-ossp (génération d'identifiants uniques)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Activer pg_trgm (recherche fuzzy / BM25-like pour hybrid retrieval)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Bases de données séparées pour isolation logique
CREATE DATABASE mlflow;
CREATE DATABASE langfuse;

-- (Optionnel : pré-créer un schéma dédié dans orchestrix)
-- CREATE SCHEMA IF NOT EXISTS orchestrix_core;
-- CREATE SCHEMA IF NOT EXISTS orchestrix_audit;
