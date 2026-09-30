"""Retrieval-Augmented Generation — Lot A.

Recherche hybride (vectorielle + BM25) avec filtres sur les métadonnées
source (josse/itemlet/public_jira/policy) et type (task/issue_metadata/...).

⚠️ RÈGLE : un chunk JOSSE effort n'est PAS sémantiquement équivalent à
   un commentaire Public Jira — les métadonnées source/type sont appliquées
   avant la sélection finale.
"""
