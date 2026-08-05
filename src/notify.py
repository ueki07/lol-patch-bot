"""Envoi vers un webhook Discord (ou stdout si aucun webhook défini).

Un seul moteur : send_blocks() reçoit des blocs [{'name', 'lines'}] où chaque
ligne est un tuple (kind, up, text). Rendu en texte simple, compact, en colonnes :
pastille 🟢 (buff) / 🔴 (nerf) / ⚪ (ajustement) + flèche 🔺/🔻. Pagination dans les
limites Discord (1024 car/champ, 25 champs/embed, ~6000 car/embed).
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

MAX_FIELD_VALUE = 1024
MAX_FIELDS = 25
CHAR_BUDGET = 5500       # marge sous la limite de 6000 car/embed
COLOR = 0x0AC8B9         # turquoise LoL
UA = "lol-patch-bot/1.0 (+https://github.com/ueki07/lol-patch-bot)"

# Pastille de couleur (texte simple, colonnes compactes, sans encadré).
DOT = {"buff": "🟢", "nerf": "🔴", "neutral": "⚪"}


def _render(kind: str, up, text: str) -> str:
    """Ligne (kind, up, text) -> texte. Pastille 🟢/🔴/⚪ + flèche 🔺/🔻."""
    if kind == "header":
        return f"**{text}**"
    if kind == "text":
        return text
    if kind == "neutral":
        return f"⚪ {text}"
    arrow = "🔺" if up else "🔻"
    return f"{DOT[kind]}{arrow} {text}"


def _post(payload: dict) -> None:
    if not WEBHOOK:
        print("[DRY-RUN] " + json.dumps(payload, ensure_ascii=False)[:1500])
        return
    data = json.dumps(payload).encode("utf-8")
    for _ in range(4):
        req = urllib.request.Request(
            WEBHOOK, data=data,
            headers={"Content-Type": "application/json", "User-Agent": UA},
        )
        try:
            with urllib.request.urlopen(req, timeout=30):
                return
        except urllib.error.HTTPError as e:
            if e.code == 429:  # rate limit : on respecte Retry-After
                time.sleep(min(float(e.headers.get("Retry-After", "1")) + 0.3, 5))
                continue
            raise
    raise RuntimeError("Échec d'envoi Discord après plusieurs tentatives")


def _chunk(rendered: list[str], budget: int) -> list[str]:
    """Regroupe des lignes en blocs de texte <= budget caractères."""
    blocks, cur, cur_len = [], [], 0
    for ln in rendered:
        ln = ln[:budget]
        if cur and cur_len + len(ln) + 1 > budget:
            blocks.append("\n".join(cur))
            cur, cur_len = [], 0
        cur.append(ln)
        cur_len += len(ln) + 1
    if cur:
        blocks.append("\n".join(cur))
    return blocks


def _fields(blocks: list[dict], inline: bool) -> list[dict]:
    fields = []
    for block in blocks:
        # Les listes (nouveaux champions/items) restent pleine largeur.
        is_list = block["name"].startswith(("🆕", "❌"))
        rendered = [_render(kind, up, text) for kind, up, text in block["lines"]]
        for i, chunk in enumerate(_chunk(rendered, MAX_FIELD_VALUE)):
            name = block["name"] if i == 0 else f"{block['name']} (suite)"
            fields.append({"name": name[:256], "value": chunk,
                           "inline": inline and not is_list})
    return fields


def send_blocks(patch: str, date: str | None, url: str, blocks: list[dict],
                source: str, inline: bool = True) -> int:
    """Publie les blocs. Renvoie le nombre de messages envoyés."""
    desc = ""
    if date:
        desc += f"📅 Sortie le **{date}**\n"
    desc += f"[📖 Notes complètes]({url})\n🟢 buff  🔴 nerf  ⚪ ajustement"
    title = f"🩹 Patch {patch} est arrivé !"

    fields = _fields(blocks, inline)
    if not fields:
        _post({"embeds": [{"title": title, "url": url, "color": COLOR,
                           "description": desc + "\n\n*Aucun changement détecté.*"}]})
        return 1

    # Un embed par message : on remplit jusqu'à 25 champs ou ~5500 caractères.
    sent, i, first = 0, 0, True
    while i < len(fields):
        embed = {"color": COLOR}
        used = 0
        if first:
            embed.update(title=title, url=url, description=desc)
            used = len(title) + len(desc)
        chunk = []
        while i < len(fields) and len(chunk) < MAX_FIELDS:
            cost = len(fields[i]["name"]) + len(fields[i]["value"])
            if chunk and used + cost > CHAR_BUDGET:
                break
            chunk.append(fields[i]); used += cost; i += 1
        embed["fields"] = chunk
        _post({"embeds": [embed]})
        sent += 1; first = False
        if i < len(fields):
            time.sleep(0.7)  # évite le rate limit du webhook
    return sent
