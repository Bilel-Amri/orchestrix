"""Client Groq — API compatible OpenAI, sans dépendance externe.

Points clés :
  - aucun nom de modèle figé : GET /models et choix dans le compte
  - response_format=json_object : syntaxe JSON garantie par Groq
  - gestion du 429 (retry-after) au lieu de planter
"""

from __future__ import annotations

import json
import os
import threading
import time

from . import httpclient as requests

BASE = "https://api.groq.com/openai/v1"

# Familles préférées, du plus capable au plus léger. On prend la première
# qui EXISTE réellement dans le compte.
PREFERENCE_QUALITE = ["llama-3.3-70b", "gpt-oss-120b", "qwen3", "kimi-k2",
                      "llama-4-maverick", "gpt-oss-20b", "llama-3.1-8b"]
_CACHE_MODELES: dict = {"liste": []}

PREFERENCE_VITESSE = ["llama-3.1-8b", "gpt-oss-20b", "llama-3.3-70b", "qwen3"]


class GroqError(RuntimeError):
    pass


class GroqClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> None:
        if api_key:
            self.api_key = api_key
        else:
            from . import reglages
            self.api_key = reglages.cle_effective()
        if not self.api_key:
            raise GroqError(
                "Clé Groq absente. Trois façons de la fournir :\n"
                "  1. dans l'interface web : vue « Réglages », champ « Clé Groq »\n"
                "  2. en variable d'environnement : export GROQ_API_KEY=gsk_...\n"
                "  3. en ligne de commande : --api-key gsk_...\n"
                "Créer une clé : https://console.groq.com/keys"
            )
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._modele_rapide_cache = ""
        self._modele_qualite_cache = model or ""
        # session HTTP : la connexion TLS est renégociée à chaque appel avec
        # urllib, soit ~200 à 400 ms perdus par requête. La session la réutilise.
        self._session = requests.Session()
        self.model = model or self.choisir_modele(PREFERENCE_QUALITE)

    # ------------------------------------------------------------------
    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Orchestrix/2.0",
        }

    def lister_modeles(self) -> list[str]:
        if _CACHE_MODELES["liste"]:
            return list(_CACHE_MODELES["liste"])
        try:
            r = self._session.get(f"{BASE}/models", headers=self._headers, timeout=20)
        except requests.RequestException as exc:
            raise GroqError(f"Impossible de joindre Groq : {exc}") from exc
        if r.status_code == 401:
            raise GroqError("Clé Groq refusée (401). Vérifie GROQ_API_KEY.")
        if r.status_code != 200:
            raise GroqError(f"Groq a répondu {r.status_code} : {r.text[:200]}")
        ids = [m.get("id", "") for m in r.json().get("data", [])]
        gardes = [i for i in ids if i and "whisper" not in i and "guard" not in i]
        _CACHE_MODELES["liste"] = list(gardes)
        return gardes

    def choisir_modele(self, preference: list[str]) -> str:
        disponibles = self.lister_modeles()
        if not disponibles:
            raise GroqError("Aucun modèle texte disponible sur ce compte Groq.")
        for pref in preference:
            for dispo in disponibles:
                if pref in dispo:
                    return dispo
        return disponibles[0]

    def modele_rapide(self) -> str:
        """Modèle léger pour l'étape ①.

        Le choix du modèle interrogeait `/models` à CHAQUE génération : un
        aller-retour réseau inutile, et une liste de modèles redemandée alors
        qu'elle ne change pas d'une minute à l'autre. On la garde en mémoire
        pour la durée du client.
        """
        if self._modele_rapide_cache:
            return self._modele_rapide_cache
        try:
            self._modele_rapide_cache = self.choisir_modele(PREFERENCE_VITESSE)
        except GroqError:
            self._modele_rapide_cache = self.model
        return self._modele_rapide_cache

    # ------------------------------------------------------------------
    def chat_json(
        self, system: str, user: str, max_tokens: int | None = None,
        model: str | None = None, temperature: float | None = None,
        jeton=None,
    ) -> dict:
        payload = {
            "model": model or self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "response_format": {"type": "json_object"},
        }
        # Le mode JSON impose des accolades : le détecteur de flux peut
        # resynchroniser le texte si la coupure à `max_tokens` survient au
        # milieu d'une chaîne (voir `_ferme_les_accolades`).
        contenu = self._post(payload, jeton=jeton)
        return _loads(_ferme_les_accolades(contenu))

    # ------------------------------------------------------------------
    def prechauffer(self) -> None:
        """Ouvre la connexion et découvre les modèles AVANT le travail.

        Le premier appel à Groq payait trois choses à la suite : la poignée de
        main TLS, l'interrogation de `/models`, puis la requête elle-même.
        Lancé au démarrage de l'interface, tout cela est déjà fait quand
        l'utilisateur clique sur « Générer ». Silencieux en cas d'échec : la
        génération saura de toute façon le signaler.
        """
        def tache():
            try:
                self.lister_modeles()
                self._session.get(f"{BASE}/models", headers=self._headers,
                                  timeout=15)
            except Exception:                    # noqa: BLE001
                pass

        threading.Thread(target=tache, daemon=True).start()

    # ------------------------------------------------------------------
    def completude(self, payload: dict, jeton=None) -> str:
        """Envoie le prompt en FLUX et signale l'avancement.

        Un plan fait 6 000 à 12 000 jetons de sortie. Groq produit environ
        300 jetons par seconde : la réponse demande donc 20 à 40 secondes.
        En flux, chaque fragment est compté au fur et à mesure, ce qui donne
        un avancement réel plutôt qu'un sablier.

        Repli automatique
        -----------------
        Si le flux ne rend rien (API qui n'accepte pas `stream`, proxy qui
        tamponne la réponse), on refait l'appel en mode normal. Mieux vaut
        perdre la progression que le plan lui-même.
        """
        if jeton:
            recus = [0]

            def compter(n):
                recus[0] = n
                jeton(n)

            texte = self._post(payload, jeton=compter)
            if not texte.strip() and not recus[0]:
                print("   ↻ flux vide — nouvel essai sans flux", flush=True)
                return self._post(payload, jeton=None)
            return texte
        return self._post(payload)

    def _post(self, payload: dict, jeton=None) -> str:
        derniere = ""
        for tentative in range(4):
            try:
                return self._post_flux(payload, jeton) if jeton else \
                       self._post_simple(payload)
            except _Reessayer as r:
                derniere = r.message
                if r.attente:
                    time.sleep(r.attente)
                if r.retirer_format:
                    payload.pop("response_format", None)
                continue
            except requests.RequestException as exc:
                derniere = str(exc)[:200]
                time.sleep(2 * (tentative + 1))
                continue

        raise GroqError(f"Appel Groq échoué : {derniere}")

    # ------------------------------------------------------------------
    def _post_flux(self, payload: dict, jeton) -> str:
        """Variante en flux : compte les jetons reçus, appelle `jeton(n)`."""
        payload = dict(payload, stream=True)
        texte: list[str] = []
        recus = 0
        statut, entetes = 0, {}
        tampon = b""
        for genre, contenu in self._session.post_flux(
                f"{BASE}/chat/completions", headers=self._headers,
                json=payload, timeout=self.timeout):
            if genre == "http":
                statut, entetes, corps = contenu
                self._traiter_statut(statut, entetes, corps, payload)
                return ""
            if genre == "entete":
                statut, entetes = contenu
                continue
            tampon += contenu
            while b"\n" in tampon:
                ligne, tampon = tampon.split(b"\n", 1)
                ligne = ligne.strip()
                if not ligne.startswith(b"data:"):
                    continue
                charge = ligne[5:].strip()
                if charge == b"[DONE]":
                    continue
                try:
                    evenement = json.loads(charge)
                except ValueError:
                    continue
                choix = (evenement.get("choices") or [{}])[0]
                morceau = (choix.get("delta") or {}).get("content") or ""
                if morceau:
                    texte.append(morceau)
                    recus += 1
                    if jeton and recus % 8 == 0:
                        try:
                            jeton(recus)
                        except Exception:            # noqa: BLE001
                            pass
        if jeton and recus:
            try:
                jeton(recus)
            except Exception:                        # noqa: BLE001
                pass
        return "".join(texte)

    def _post_simple(self, payload: dict) -> str:
        """Variante d'un bloc (utilisée pour les petites réponses)."""
        r = self._session.post(
            f"{BASE}/chat/completions", headers=self._headers,
            json=payload, timeout=self.timeout)
        self._traiter_statut(r.status_code, r.headers, r.content, payload)
        return r.json().get("choices", [{}])[0].get("message", {}).get("content", "")

    def _traiter_statut(self, code: int, entetes: dict, corps: bytes,
                        payload: dict) -> None:
        """Lève l'exception qui convient selon le code HTTP.

        `_Reessayer` est interne : elle porte le délai à respecter et, pour un
        modèle sans mode JSON, la correction à appliquer au prompt.
        """
        if code == 429:
            # les en-têtes du flux arrivent avec leur casse d'origine
            entetes = {str(k).lower(): v for k, v in (entetes or {}).items()}
            attente = _retry_after_entetes(entetes)
            print(f"   ⏳ quota Groq atteint — attente {attente}s", flush=True)
            raise _Reessayer("quota", attente=attente)
        if code == 401:
            raise GroqError("Clé Groq refusée (401).")
        if code == 413:
            detail = corps.decode("utf-8", "replace").strip()

            taille_payload = len(
                json.dumps(payload, ensure_ascii=False).encode("utf-8")
            )

            messages = payload.get("messages", [])
            taille_systeme = sum(
                len(m.get("content", "")) for m in messages
                if m.get("role") == "system"
            )
            taille_utilisateur = sum(
                len(m.get("content", "")) for m in messages
                if m.get("role") == "user"
            )

            modele = payload.get("model", "inconnu")
            tokens = payload.get("max_tokens", "inconnu")

            raise GroqError(
                "ERREUR GROQ HTTP 413\\n"
                f"Modèle : {modele}\\n"
                f"Taille du JSON envoyé : {taille_payload:,} octets\\n"
                f"Prompt système : {taille_systeme:,} caractères\\n"
                f"Prompt utilisateur : {taille_utilisateur:,} caractères\\n"
                f"Tokens de sortie demandés : {tokens}\\n"
                f"Détail renvoyé par Groq : {detail[:1200]}"
            )
        texte = corps.decode("utf-8", "replace")
        if code == 400 and "json" in texte.lower():
            raise _Reessayer("modèle sans mode JSON", retirer_format=True)
        if code != 200:
            raise _Reessayer(f"{code} {texte[:180]}", attente=2)


def _ferme_les_accolades(texte: str) -> str:
    """Referme un objet JSON tronqué par la limite de jetons.

    Groq coupe net à `max_tokens`. Sur un plan de 10 000 jetons, cette
    coupure tombait autrefois au milieu du JSON : tout le travail déjà écrit
    était perdu et l'appel devait être repayé en entier. Le flux permettait
    de repérer la troncature ; cette reprise garde ce qui a été produit en
    refermant proprement les structures ouvertes.
    """
    t = texte.strip()
    if not t.startswith("{"):
        return texte                      # pas du JSON : rien à refermer
    pile: list[str] = []
    dans_chaine = False
    echappe = False
    for c in t:
        if dans_chaine:
            if echappe:
                echappe = False
            elif c == "\\":
                echappe = True
            elif c == '"':
                dans_chaine = False
            continue
        if c == '"':
            dans_chaine = True
        elif c in "{[":
            pile.append(c)
        elif c in "}]" and pile:
            pile.pop()
    if not pile and not dans_chaine:
        return texte                      # déjà complet
    sortie = t
    if dans_chaine:
        sortie += '"'
    # on retire une éventuelle fin de champ incomplète
    while sortie.rstrip().endswith((",", ":")):
        sortie = sortie.rstrip()[:-1]
    for ouverture in reversed(pile):
        sortie += "}" if ouverture == "{" else "]"
    return sortie


class _Reessayer(Exception):
    """Signal interne : nouvel essai, éventuellement après une correction."""

    def __init__(self, message: str, attente: int = 0, retirer_format: bool = False):
        super().__init__(message)
        self.message = message
        self.attente = attente
        self.retirer_format = retirer_format


def _retry_after_entetes(entetes: dict) -> int:
    for nom in ("retry-after", "x-ratelimit-reset-requests", "x-ratelimit-reset-tokens"):
        v = (entetes or {}).get(nom)
        if v:
            chiffres = "".join(c for c in str(v) if c.isdigit())
            if chiffres:
                return min(int(chiffres), 60)
    return 10


def _retry_after(r: requests.Response) -> int:
    for entete in ("retry-after", "x-ratelimit-reset-requests", "x-ratelimit-reset-tokens"):
        v = r.headers.get(entete)
        if v:
            chiffres = "".join(c for c in v if c.isdigit())
            if chiffres:
                return min(int(chiffres), 60)
    return 10


def _sans_virgule_finale(t: str) -> str:
    """Retire les virgules qui précèdent une fermeture : {…,} ou […,].

    Une réponse tronquée se termine souvent par une virgule ; en recollant les
    accolades on obtient « {"a": 1,} », que les parseurs JSON refusent — et
    Python 3.14 le refuse plus strictement encore qu'avant. La virgule est
    ignorée hors des chaînes de caractères, jamais à l'intérieur.
    """
    out: list[str] = []
    chaine = False
    i = 0
    while i < len(t):
        c = t[i]
        if chaine:
            out.append(c)
            if c == "\\" and i + 1 < len(t):
                out.append(t[i + 1])
                i += 2
                continue
            if c == '"':
                chaine = False
            i += 1
            continue
        if c == '"':
            chaine = True
            out.append(c)
            i += 1
            continue
        if c == ",":
            j = i + 1
            while j < len(t) and t[j] in " \t\r\n":
                j += 1
            if j >= len(t) or t[j] in "}]":
                i += 1                      # virgule orpheline : supprimée
                continue
        out.append(c)
        i += 1
    return "".join(out)


def _reparer(t: str) -> str:
    """Referme un JSON tronqué : chaîne ouverte, crochets, accolades."""
    chaine, pile, i = False, [], 0
    while i < len(t):
        c = t[i]
        if chaine:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                chaine = False
        else:
            if c == '"':
                chaine = True
            elif c in "[{":
                pile.append(c)
            elif c in "]}":
                if pile:
                    pile.pop()
        i += 1
    fermeture = ('"' if chaine else "") + "".join(
        "}" if c == "{" else "]" for c in reversed(pile)
    )
    return t + fermeture


def _loads(raw: str) -> dict:
    """Lit le JSON du modèle, en réparant ce qui peut l'être.

    Trois tentatives, de la plus confiante à la plus interventionniste :
      1. le texte tel quel ;
      2. après retrait des virgules finales ;
      3. après fermeture des structures ouvertes et retrait des virgules.

    Si les trois échouent, l'erreur est explicite : mieux vaut un message clair
    qu'une trace de décodage JSON qui ne dit pas quoi faire.
    """
    t = raw.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{") :] if "{" in t else t

    for tentative, texte in enumerate((t, _sans_virgule_finale(t))):
        try:
            d = json.loads(texte)
            if isinstance(d, dict):
                return d
        except json.JSONDecodeError:
            continue

    debut = t.find("{")
    if debut == -1:
        raise GroqError("Aucun objet JSON dans la réponse du modèle")
    repare = _sans_virgule_finale(_reparer(t[debut:]))
    try:
        d = json.loads(repare)
    except json.JSONDecodeError as exc:
        raise GroqError(
            "réponse JSON illisible — le modèle a probablement été coupé "
            f"(max_tokens trop bas ?) : {exc.msg} à la position {exc.pos}"
        ) from exc
    if not isinstance(d, dict):
        raise GroqError("La réponse JSON n'est pas un objet")
    return d
