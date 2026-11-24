"""Réglages locaux de la machine — pour l'instant, la clé Groq.

Trois façons de fournir la clé, dans cet ordre de priorité :

  1. `--api-key gsk_...` sur la ligne de commande (prioritaire, jamais écrit
     sur le disque) ;
  2. la variable d'environnement `GROQ_API_KEY` (méthode classique, pour un
     serveur ou un script) ;
  3. le fichier `donnees/reglages.json`, écrit quand on saisit la clé depuis
     l'interface web.

Le fichier est créé avec les droits 600 : lisible par votre seul compte.
Ce n'est pas un coffre-fort — un secret en clair sur disque reste un secret
en clair — mais il n'est lisible ni par les autres comptes de la machine, ni
par le navigateur : l'interface n'affiche jamais la clé, seulement sa présence.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

_RACINE = Path(__file__).resolve().parent.parent / "donnees"
_FICHIER = _RACINE / "reglages.json"


def _lire() -> dict:
    try:
        return json.loads(_FICHIER.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _ecrire(d: dict) -> None:
    _RACINE.mkdir(parents=True, exist_ok=True)
    _FICHIER.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(_FICHIER, stat.S_IRUSR | stat.S_IWUSR)      # 600
    except OSError:
        pass


def cle_enregistree() -> str:
    """Clé saisie depuis l'interface, ou chaîne vide."""
    return str(_lire().get("groq_api_key") or "").strip()


def enregistrer_cle(cle: str) -> None:
    d = _lire()
    cle = str(cle or "").strip()
    if cle:
        d["groq_api_key"] = cle
    else:
        d.pop("groq_api_key", None)
    _ecrire(d)


def effacer_cle() -> None:
    enregistrer_cle("")


def source_cle() -> str:
    """D'où vient la clé réellement utilisée — sans jamais la révéler."""
    if os.environ.get("GROQ_API_KEY", "").strip():
        return "variable d'environnement"
    if cle_enregistree():
        return "fichier local"
    return ""


def cle_effective() -> str:
    return (os.environ.get("GROQ_API_KEY", "").strip()
            or cle_enregistree())


def masque(cle: str) -> str:
    """Forme affichable : garde le préfixe, cache le reste."""
    cle = str(cle or "")
    if len(cle) < 12:
        return "•" * 8
    return cle[:6] + "…" + "•" * 6 + cle[-2:]
