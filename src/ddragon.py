"""Accès à l'API Data Dragon de Riot (officielle, gratuite, sans clé).

DDragon expose les données de jeu versionnées et localisées. On l'utilise pour :
  - détecter la dernière version (versions.json)
  - récupérer les données complètes des champions et des items pour une version
    donnée, en français (locale fr_FR).
"""

from __future__ import annotations

import json
import urllib.request

BASE = "https://ddragon.leagueoflegends.com"
LOCALE = "fr_FR"
UA = "lol-patch-bot/1.0 (+https://github.com)"


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
