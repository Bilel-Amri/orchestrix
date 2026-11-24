"""Client HTTP minimal sur la bibliothèque standard.

Pourquoi ce fichier existe
--------------------------
Le projet n'utilisait `requests` que pour six appels GET et deux appels POST.
Or `requests` traîne derrière elle `charset_normalizer`, `urllib3`, `idna` et
`certifi` : cinq paquets à installer, et des conflits de résolution pip sur
certaines machines. Cette petite couche reproduit l'interface réellement
utilisée — `.status_code`, `.text`, `.json()`, `.headers` — avec `urllib`
seulement. Installer Orchestrix ne demande donc plus **aucun** paquet externe.

Pourquoi `http.client` et pas `urllib.request`
----------------------------------------------
`urllib.request.urlopen` ferme la connexion après chaque réponse : chaque
appel PayPal le prix d'une poignée de main TCP **et** d'une négociation TLS,
soit 150 à 400 ms. Sur une génération qui enchaîne huit appels à la même API,
c'est deux secondes perdues sans rien produire. La classe `Session` ci-dessous
garde la connexion ouverte et la réutilise.

Ce qui est fourni :

    get(url, headers=..., timeout=..., params=...)          -> Reponse
    post(url, headers=..., timeout=..., json=..., data=...) -> Reponse
    Session()                                               -> connexions gardées
    Session.post_flux(...)                                  -> lecture en flux
    RequestException                                        -> exception commune

Les erreurs réseau (DNS, refus de connexion, délai dépassé, TLS) sont
converties en `RequestException`, comme le faisait `requests`.
"""

from __future__ import annotations

import http.client
import json as _json
import socket
import ssl
import threading
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

__all__ = ["get", "post", "Session", "Reponse", "Response",
           "RequestException", "defaut_entetes"]

UA = ("Mozilla/5.0 (compatible; Orchestrix/1.0; "
      "+https://example.org) Python-urllib")

# un contexte TLS par défaut, partagé : le certificat racine système est utilisé
_CONTEXTE = ssl.create_default_context()

# erreurs qui justifient un nouvel essai sur une connexion neuve
_PANNE = (http.client.HTTPException, ConnectionError, socket.timeout,
          TimeoutError, ssl.SSLError, OSError)


class RequestException(Exception):
    """Erreur réseau : remplace `requests.RequestException`."""


class Reponse:
    """Réponse HTTP minimale, calquée sur l'objet de `requests`."""

    __slots__ = ("status_code", "headers", "content", "url", "raison")

    def __init__(self, status_code: int, headers: dict, content: bytes,
                 url: str = "", raison: str = "") -> None:
        self.status_code = status_code
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.content = content or b""
        self.url = url
        self.raison = raison

    # ── corps ────────────────────────────────────────────────────────
    @property
    def text(self) -> str:
        """Corps décodé. L'en-tête Content-Type est prioritaire, UTF-8 sinon."""
        encodage = None
        entete = self.headers.get("content-type", "")
        if "charset=" in entete:
            encodage = entete.split("charset=", 1)[1].split(";")[0].strip().strip('"')
        for essai in (encodage, "utf-8", "latin-1"):
            if not essai:
                continue
            try:
                return self.content.decode(essai, errors="strict")
            except (LookupError, UnicodeDecodeError):
                continue
        # dernier recours : on ne perd jamais le contenu
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        """Corps interprété comme du JSON. Lève ValueError si ce n'en est pas."""
        return _json.loads(self.text)

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RequestException(f"HTTP {self.status_code} pour {self.url}")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Reponse [{self.status_code}] {self.url[:70]}>"


# alias anglais, pour un éventuel code écrit à l'anglaise
Response = Reponse


# ──────────────────────────────────────────────────────────────────────
# Session : connexions gardées ouvertes
# ──────────────────────────────────────────────────────────────────────
class Session:
    """Session HTTP réutilisable.

    Une connexion est conservée par couple (hôte, fil d'exécution). Le fil
    compte parce qu'une même session peut servir plusieurs traductions en
    parallèle : deux requêtes simultanées ne peuvent pas partager la même
    connexion HTTP/1.1, mais elles peuvent chacune garder la leur.

    Toute panne de connexion est suivie d'un nouvel essai sur une connexion
    neuve : les serveurs ferment les connexions inactives au bout de quelques
    secondes, et une réponse perdue pour cette raison ne doit pas remonter
    comme une erreur.
    """

    def __init__(self) -> None:
        self._connexions: dict[tuple, http.client.HTTPConnection] = {}
        self._verrou = threading.Lock()

    # -- interne ----------------------------------------------------
    def _cle(self, url: str, timeout: float) -> tuple:
        u = urllib.parse.urlsplit(url)
        return (u.scheme or "https", u.netloc, timeout, threading.get_ident())

    def _neuve(self, url: str, timeout: float) -> http.client.HTTPConnection:
        u = urllib.parse.urlsplit(url)
        if (u.scheme or "https") == "https":
            return http.client.HTTPSConnection(u.netloc, timeout=timeout,
                                               context=_CONTEXTE)
        return http.client.HTTPConnection(u.netloc, timeout=timeout)

    def _obtenir(self, url: str, timeout: float) -> http.client.HTTPConnection:
        cle = self._cle(url, timeout)
        with self._verrou:
            conn = self._connexions.get(cle)
            if conn is None:
                conn = self._neuve(url, timeout)
                self._connexions[cle] = conn
            return conn

    def _oublier(self, url: str, timeout: float, conn) -> None:
        cle = self._cle(url, timeout)
        with self._verrou:
            if self._connexions.get(cle) is conn:
                self._connexions.pop(cle, None)
        try:
            conn.close()
        except Exception:                        # noqa: BLE001
            pass

    def _ouvrir(self, methode: str, url: str, entetes: dict, corps: bytes | None,
                timeout: float):
        """Envoie la requête et rend (connexion, réponse), avec un réessai."""
        u = urllib.parse.urlsplit(url)
        chemin = (u.path or "/") + (f"?{u.query}" if u.query else "")
        derniere: Exception | None = None
        for essai in (0, 1):
            conn = self._obtenir(url, timeout)
            try:
                conn.request(methode, chemin, body=corps,
                             headers=defaut_entetes(entetes))
                return conn, conn.getresponse()
            except _PANNE as exc:
                derniere = exc
                self._oublier(url, timeout, conn)
                if isinstance(exc, socket.timeout) or isinstance(exc, TimeoutError):
                    break                    # inutile d'insister après un délai
        raison = getattr(derniere, "reason", derniere)
        raise RequestException(f"{methode} {url} : {raison}") from derniere

    # -- interface --------------------------------------------------
    def request(self, methode: str, url: str, headers=None, timeout: float = 30,
                params: dict | None = None, json: Any = None,
                data: dict | None = None) -> Reponse:
        entetes = dict(headers or {})
        corps = None
        if json is not None:
            corps = _json.dumps(json, ensure_ascii=False).encode("utf-8")
            entetes.setdefault("Content-Type", "application/json")
        elif data is not None:
            corps = urllib.parse.urlencode(data).encode("utf-8")
            entetes.setdefault("Content-Type",
                               "application/x-www-form-urlencoded")
        if params:
            sep = "&" if urllib.parse.urlsplit(url).query else "?"
            url = url + sep + urllib.parse.urlencode(params)

        conn, rep = self._ouvrir(methode, url, entetes, corps, timeout)
        try:
            contenu = rep.read()
            en_tetes = dict(rep.getheaders())
            statut, raison = rep.status, rep.reason
            # une réponse non lue en entier casse la connexion : on la referme
            if rep.will_close or statut >= 500:
                self._oublier(url, timeout, conn)
        except _PANNE as exc:
            self._oublier(url, timeout, conn)
            raise RequestException(f"{methode} {url} : {exc}") from exc
        return Reponse(statut, en_tetes, contenu, url, raison)

    def get(self, url, headers=None, timeout=30, params=None, **extra):
        return self.request("GET", url, headers, timeout, params)

    def post(self, url, headers=None, timeout=60, json=None, data=None, **extra):
        return self.request("POST", url, headers, timeout, None, json, data)

    def post_flux(self, url, headers=None, timeout=180, json=None):
        """POST JSON et lecture de la réponse au fil de l'eau.

        Rend un itérateur qui produit d'abord `("entete", (statut, en-têtes))`,
        puis des `("corps", octets)`. Les réponses d'erreur (4xx, 5xx) sont
        rendues d'un bloc sous la forme `("http", (statut, en-têtes, corps))` :
        l'appelant peut ainsi réagir à un 429 sans avoir attendu la fin d'un
        corps qui n'arrivera jamais.
        """
        corps = _json.dumps(json, ensure_ascii=False).encode("utf-8") \
            if json is not None else b""
        entetes = dict(headers or {})
        entetes.setdefault("Content-Type", "application/json")

        conn, rep = self._ouvrir("POST", url, entetes, corps, timeout)
        try:
            en_tetes = dict(rep.getheaders())
            if rep.status >= 400:
                donnees = rep.read()
                self._oublier(url, timeout, conn)
                yield ("http", (rep.status, en_tetes, donnees))
                return
            yield ("entete", (rep.status, en_tetes))
            while True:
                try:
                    morceau = rep.read(2048)
                except _PANNE as exc:
                    raise RequestException(f"flux interrompu : {exc}") from exc
                if not morceau:
                    break
                yield ("corps", morceau)
            if rep.will_close:
                self._oublier(url, timeout, conn)
        finally:
            try:
                rep.close()
            except Exception:                    # noqa: BLE001
                pass

    def fermer(self) -> None:
        """Ferme toutes les connexions gardées."""
        with self._verrou:
            connexions = list(self._connexions.values())
            self._connexions.clear()
        for conn in connexions:
            try:
                conn.close()
            except Exception:                    # noqa: BLE001
                pass

    # `close` pour l'analogie avec `requests.Session`
    close = fermer

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, *_a) -> None:
        self.fermer()


# ──────────────────────────────────────────────────────────────────────
# Fonctions de module : une session partagée, par fil d'exécution
# ──────────────────────────────────────────────────────────────────────
_LOCALE = threading.local()


def session_courante() -> Session:
    """La session du fil courant, créée à la demande.

    Les neuf sources sont interrogées depuis neuf fils différents : chacune a
    donc sa propre connexion, et aucune n'attend après les autres.
    """
    s = getattr(_LOCALE, "session", None)
    if s is None:
        s = Session()
        _LOCALE.session = s
    return s


def defaut_entetes(entetes: dict | None = None) -> dict:
    base = {"User-Agent": UA, "Accept": "*/*"}
    if entetes:
        base.update({k: v for k, v in entetes.items() if v is not None})
    return base


def _requete(methode: str, url: str, entetes: dict | None = None,
             timeout: float = 30, params: dict | None = None,
             corps: bytes | None = None) -> Reponse:
    """Compatibilité : même signature que l'ancienne version `urllib`."""
    s = session_courante()
    if params:
        sep = "&" if urllib.parse.urlsplit(url).query else "?"
        url = url + sep + urllib.parse.urlencode(params)
    return s.request(methode, url, entetes, timeout, None, None, None) \
        if corps is None else _requete_corps(s, methode, url, entetes, timeout, corps)


def _requete_corps(session: Session, methode: str, url: str, entetes, timeout,
                   corps: bytes) -> Reponse:
    e = dict(entetes or {})
    e.setdefault("Content-Type", "application/octet-stream")
    conn, rep = session._ouvrir(methode, url, e, corps, timeout)
    try:
        return Reponse(rep.status, dict(rep.getheaders()), rep.read(), url,
                       rep.reason)
    finally:
        try:
            rep.close()
        except Exception:                        # noqa: BLE001
            pass


def get(url: str, headers: dict | None = None, timeout: float = 30,
        params: dict | None = None, **extra) -> Reponse:
    """GET. Les paramètres inconnus sont ignorés, comme avec `requests`."""
    return session_courante().request("GET", url, headers, timeout, params)


def post(url: str, headers: dict | None = None, timeout: float = 60,
         json: Any = None, data: dict | None = None, **extra) -> Reponse:
    """POST en JSON (argument `json`) ou en formulaire (argument `data`)."""
    return session_courante().request("POST", url, headers, timeout, None,
                                      json, data)
