"""Accès à l'API Data Dragon de Riot (officielle, gratuite, sans clé).

DDragon expose les données de jeu versionnées et localisées. On l'utilise pour :
  - détecter la dernière version (versions.json)
  - récupérer les données complètes des champions et des items pour une version
    donnée, en français (locale fr_FR).
"""

from __future__ import annotations

import email.utils
import json
import urllib.request

BASE = "https://ddragon.leagueoflegends.com"
LOCALE = "fr_FR"
UA = "lol-patch-bot/1.0 (+https://github.com)"

MOIS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def _get_json(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def latest_versions() -> list[str]:
    """Liste des versions, la plus récente en tête. Ex: ['15.15.1', '15.14.1', ...]."""
    return _get_json(f"{BASE}/api/versions.json")


def champions_full(version: str) -> dict:
    """Toutes les données champions (stats + sorts) pour une version, en FR.

    Renvoie le dict `data` indexé par nom interne de champion (ex: 'Garen').
    """
    url = f"{BASE}/cdn/{version}/data/{LOCALE}/championFull.json"
    return _get_json(url)["data"]


def items(version: str) -> dict:
    """Toutes les données items pour une version, en FR. Indexé par id (str)."""
    url = f"{BASE}/cdn/{version}/data/{LOCALE}/item.json"
    return _get_json(url)["data"]


def patch_date(version: str) -> str | None:
    """Date effective du patch, en français (ex: '28 juillet 2026').

    DDragon ne fournit pas de date : on lit l'en-tête HTTP Last-Modified des
    données de la version, qui correspond à leur mise en ligne = jour du patch.
    """
    url = f"{BASE}/cdn/{version}/data/{LOCALE}/championFull.json"
    req = urllib.request.Request(url, headers={"User-Agent": UA}, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            last_modified = resp.headers.get("Last-Modified")
    except Exception:
        return None
    if not last_modified:
        return None
    dt = email.utils.parsedate_to_datetime(last_modified)
    return f"{dt.day} {MOIS_FR[dt.month - 1]} {dt.year}"
