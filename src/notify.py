"""Envoi des embeds vers un webhook Discord (ou stdout si aucun webhook défini)."""

from __future__ import annotations

import json
import os
import urllib.request

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

# Limites Discord
MAX_EMBEDS_PER_MSG = 10
MAX_FIELDS_PER_EMBED = 25
MAX_FIELD_VALUE = 1024
MAX_DESC = 4096
COLOR = 0x0AC8B9  # turquoise LoL


def _post(payload: dict) -> None:
    if not WEBHOOK:
        print("[DRY-RUN] Pas de DISCORD_WEBHOOK_URL — payload :")
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:4000])
        return
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        WEBHOOK,
        data=data,
        headers={
            "Content-Type": "application/json",
            # Discord (via Cloudflare) rejette le User-Agent par défaut de Python.
            "User-Agent": "lol-patch-bot/1.0 (+https://github.com/ueki07/lol-patch-bot)",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status >= 300:
            raise RuntimeError(f"Discord a répondu {resp.status}")


def _chunk_field_value(lines: list[str]) -> list[str]:
    """Découpe une liste de lignes en blocs <= MAX_FIELD_VALUE caractères."""
    blocks, cur = [], ""
    for ln in lines:
        if len(cur) + len(ln) + 1 > MAX_FIELD_VALUE:
            blocks.append(cur.rstrip())
            cur = ""
        cur += ln + "\n"
    if cur.strip():
        blocks.append(cur.rstrip())
    return blocks


def build_fields(champ_diff: dict, item_diff: dict) -> list[dict]:
    fields: list[dict] = []

    if champ_diff["added"]:
        fields.append({"name": "🆕 Nouveaux champions",
                       "value": ", ".join(champ_diff["added"])[:MAX_FIELD_VALUE],
                       "inline": False})
    if champ_diff["removed"]:
        fields.append({"name": "❌ Champions retirés",
                       "value": ", ".join(champ_diff["removed"])[:MAX_FIELD_VALUE],
                       "inline": False})

    for champ, lines in champ_diff["changed"].items():
        for i, block in enumerate(_chunk_field_value(lines)):
            name = champ if i == 0 else f"{champ} (suite)"
            fields.append({"name": name, "value": block, "inline": True})

    if item_diff["added"]:
        fields.append({"name": "🆕 Nouveaux items",
                       "value": ", ".join(item_diff["added"])[:MAX_FIELD_VALUE],
                       "inline": False})
    if item_diff["removed"]:
        fields.append({"name": "❌ Items retirés",
                       "value": ", ".join(item_diff["removed"])[:MAX_FIELD_VALUE],
                       "inline": False})
    for block in _chunk_field_value(item_diff["price"]):
        fields.append({"name": "💰 Prix des items", "value": block, "inline": False})

    return fields


def send_patch(version: str, prev: str, champ_diff: dict, item_diff: dict) -> None:
    fields = build_fields(champ_diff, item_diff)
    header = {
        "title": f"🩹 Patch {version} est arrivé !",
        "url": _notes_url(version),
        "color": COLOR,
        "description": (
            f"Changements détectés par rapport à **{prev}**.\n"
            f"[📖 Notes officielles]({_notes_url(version)})"
        ),
    }

    if not fields:
        header["description"] += "\n\n*Aucun changement de data détecté (patch mineur/hotfix).*"
        _post({"embeds": [header]})
        return

    # On répartit les fields sur plusieurs embeds (max 25 fields/embed).
    embeds = [header]
    for i in range(0, len(fields), MAX_FIELDS_PER_EMBED):
        chunk = fields[i:i + MAX_FIELDS_PER_EMBED]
        if i == 0:
            header["fields"] = chunk
        else:
            embeds.append({"color": COLOR, "fields": chunk})

    # Puis on découpe en messages de max 10 embeds.
    for i in range(0, len(embeds), MAX_EMBEDS_PER_MSG):
        _post({"embeds": embeds[i:i + MAX_EMBEDS_PER_MSG]})


def _notes_url(version: str) -> str:
    # 15.15.1 -> 15-15 ; l'URL officielle FR suit ce format.
    major_minor = "-".join(version.split(".")[:2])
    return f"https://www.leagueoflegends.com/fr-fr/news/game-updates/patch-{major_minor}-notes/"
