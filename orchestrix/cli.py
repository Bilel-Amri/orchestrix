"""Ligne de commande.

    export GROQ_API_KEY=gsk_...
    python -m orchestrix --brief "..."
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .agent import Orchestrix
from .llm import GroqClient, GroqError


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="orchestrix", description="Plan de projet sourcé via Groq."
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--brief", help="demande du chef de projet")
    g.add_argument("--brief-file", help="fichier texte")
    g.add_argument("--models", action="store_true", help="lister les modèles du compte")
    g.add_argument("--ui", action="store_true",
                   help="ouvrir l'interface graphique dans le navigateur")
    p.add_argument("--api-key", help="clé Groq (ou variable GROQ_API_KEY)")
    p.add_argument("--model", help="forcer un modèle (défaut : meilleur disponible)")
    p.add_argument("--out", default="out", help="dossier de sortie")
    p.add_argument("--port", type=int, default=8402, help="port de l'interface (défaut 8402)")
    p.add_argument("--no-open", action="store_true",
                   help="ne pas ouvrir le navigateur automatiquement")
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args(argv)

    if a.ui:
        from .server import servir
        servir(port=a.port, ouvrir=not a.no_open)
        return 0

    try:
        llm = GroqClient(api_key=a.api_key, model=a.model)
    except GroqError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    if a.models:
        try:
            for m in llm.lister_modeles():
                print(("→ " if m == llm.model else "  ") + m)
        except GroqError as e:
            print(f"❌ {e}", file=sys.stderr)
            return 1
        return 0

    brief = a.brief or Path(a.brief_file).read_text(encoding="utf-8").strip()
    if len(brief) < 10:
        print("❌ Brief trop court.", file=sys.stderr)
        return 2

    print(f"✅ Groq · modèle {llm.model}\n")
    agent = Orchestrix(llm=llm, verbose=not a.quiet)
    try:
        res = agent.run(brief)
    except GroqError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n⏹ interrompu.", file=sys.stderr)
        return 130
    except Exception as e:                     # noqa: BLE001
        # Aucune trace technique pour l'utilisateur : un message clair, et la
        # trace complète derrière une variable d'environnement.
        print(f"❌ erreur inattendue : {type(e).__name__}: {e}", file=sys.stderr)
        if os.environ.get("PLANAGENT_DEBUG"):
            import traceback
            traceback.print_exc()
        else:
            print("   (relancez avec PLANAGENT_DEBUG=1 pour la trace complète)",
                  file=sys.stderr)
        return 1

    j, m = agent.sauver(res, a.out)
    print("\n" + "─" * 62)
    print(res.to_markdown())
    print("─" * 62)
    print(f"💾 {j}\n💾 {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
