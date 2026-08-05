"""Envoi des embeds vers un webhook Discord (ou stdout si aucun webhook défini).

Les changements buff / nerf / neutral sont rendus dans des blocs de code ```diff```
que Discord colore : les lignes en '+' apparaissent en vert (buff), en '-' en
rouge (nerf), et sans préfixe en gris (neutre, ex: valeurs d'effets de sorts).
"""

from __future__ import annotations

import json
import os
import urllib.request

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

# Limites Discord
MAX_EMBEDS_PER_MSG = 10
MAX_FIELDS_PER_EMBED = 25
MAX_FIELD_VALUE = 1024
COLOR = 0x0AC8B9  # turquoise LoL

DIFF_OPEN = "```diff\n"
DIFF_CLOSE = "\n```"
PREFIX = {"buff": "+ ", "nerf": "- ", "neutral": "  "}


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


def _diff_blocks(entries: list[tuple[str, str]]) -> list[str]:
    """Transforme des (kind, texte) en un ou plusieurs blocs ```diff``` <= 1024 car."""
    budget = MAX_FIELD_VALUE - len(DIFF_OPEN) - len(DIFF_CLOSE)
    blocks, cur, cur_len = [], [], 0
    for kind, text in entries:
        line = PREFIX.get(kind, "  ") + text
        if cur and cur_len + len(line) + 1 > budget:
            blocks.append(DIFF_OPEN + "\n".join(cur) + DIFF_CLOSE)
            cur, cur_len = [], 0
        cur.append(line)
        cur_len += len(line) + 1
    if cur:
        blocks.append(DIFF_OPEN + "\n".join(cur) + DIFF_CLOSE)
    return blocks


def _list_field(name: str, names: list[str]) -> dict:
    return {"name": name, "value": ", ".join(names)[:MAX_FIELD_VALUE], "inline": False}


def build_fields(champ_diff: dict, item_diff: dict) -> list[dict]:
    fields: list[dict] = []

    if champ_diff["added"]:
        fields.append(_list_field("🆕 Nouveaux champions", champ_diff["added"]))
    if champ_diff["removed"]:
        fields.append(_list_field("❌ Champions retirés", champ_diff["removed"]))

    for champ, entries in champ_diff["changed"].items():
        for i, block in enumerate(_diff_blocks(entries)):
            name = champ if i == 0 else f"{champ} (suite)"
            fields.append({"name": name, "value": block, "inline": True})

    if item_diff["added"]:
        fields.append(_list_field("🆕 Nouveaux items", item_diff["added"]))
    if item_diff["removed"]:
        fields.append(_list_field("❌ Items retirés", item_diff["removed"]))
    for block in _diff_blocks(item_diff["price"]):
        fields.append({"name": "💰 Prix des items", "value": block, "inline": False})

    return fields


def send_patch(version: str, prev: str, champ_diff: dict, item_diff: dict,
               date: str | None = None) -> None:
    fields = build_fields(champ_diff, item_diff)
    desc = ""
    if date:
        desc += f"📅 Sortie le **{date}**\n"
    desc += (
        f"Changements détectés par rapport à **{prev}**.\n"
        f"[📖 Notes officielles]({_notes_url(version)})\n"
        f"🟢 buff  🔴 nerf  ⚪ ajustement"
    )
    header = {
        "title": f"🩹 Patch {version} est arrivé !",
        "url": _notes_url(version),
        "color": COLOR,
        "description": desc,
    }

    if not fields:
        header["description"] += "\n\n*Aucun changement de data détecté (patch mineur/hotfix).*"
        _post({"embeds": [header]})
        return

    # Répartition des fields sur plusieurs embeds (max 25 fields/embed).
    embeds = [header]
    for i in range(0, len(fields), MAX_FIELDS_PER_EMBED):
        chunk = fields[i:i + MAX_FIELDS_PER_EMBED]
        if i == 0:
            header["fields"] = chunk
        else:
            embeds.append({"color": COLOR, "fields": chunk})

    # Puis découpage en messages de max 10 embeds.
    for i in range(0, len(embeds), MAX_EMBEDS_PER_MSG):
        _post({"embeds": embeds[i:i + MAX_EMBEDS_PER_MSG]})


def _notes_url(version: str) -> str:
    # 15.15.1 -> 15-15 ; l'URL officielle FR suit ce format.
    major_minor = "-".join(version.split(".")[:2])
    return f"https://www.leagueoflegends.com/fr-fr/news/game-updates/patch-{major_minor}-notes/"
