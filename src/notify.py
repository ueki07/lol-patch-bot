"""Envoi vers un webhook Discord (ou stdout si aucun webhook défini).

Un seul moteur : send_blocks() reçoit des blocs [{'name', 'lines'}] où chaque
ligne est un tuple (kind, up, text). Rendu via un bloc de code ANSI : flèche ▲
verte pour un buff, ▼ rouge pour un nerf (seule façon d'avoir une flèche colorée
sur Discord). Pagination dans les limites Discord (1024 car/champ, 25 champs/embed,
~6000 car/embed).
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

# Codes ANSI rendus par Discord dans un bloc ```ansi.
_GREEN, _RED, _BOLD, _RESET = "[1;32m", "[1;31m", "[1;37m", "[0m"
FENCE_OPEN, FENCE_CLOSE = "```ansi\n", "\n```"


def _render(kind: str, up, text: str) -> str:
    """Ligne (kind, up, text) -> texte ANSI. Flèche ▲ verte (buff) / ▼ rouge (nerf).

    La flèche suit le verdict, pas le sens du nombre : baisser un coût ou un CD
    est un buff, donc ▲ vert, même si la valeur descend. Faire l'inverse donnait
    des lignes vertes fléchées vers le bas (« Q Coût 35→30 »), illisibles. Le
    sens du nombre est déjà lisible dans le « avant→après » du texte.
    """
    if kind == "header":
        return f"{_BOLD}{text}{_RESET}"
    if kind == "text":
        return text
    if kind == "neutral":
        return f"  {text}"
    color = _GREEN if kind == "buff" else _RED
    arrow = "▲" if kind == "buff" else "▼"
    return f"{color}{arrow} {text}{_RESET}"


def _post(payload: dict) -> None:
    if not WEBHOOK:
        print("[DRY-RUN] " + json.dumps(payload, ensure_ascii=False)[:1500])
        return
    data = json.dumps(payload).encode("utf-8")
    for attempt in range(4):
        req = urllib.request.Request(
            WEBHOOK, data=data,
            headers={"Content-Type": "application/json", "User-Agent": UA},
        )
        try:
            with urllib.request.urlopen(req, timeout=30):
                return
        except urllib.error.HTTPError as e:
            if e.code == 429:  # rate limit : on respecte Retry-After
                retry = float(e.headers.get("Retry-After", "1"))
                time.sleep(min(retry + 0.3, 5))
                continue
            raise
    raise RuntimeError("Échec d'envoi Discord après plusieurs tentatives")


def _chunk(rendered: list[str], budget: int, pre: str, post: str) -> list[str]:
    """Regroupe des lignes rendues en blocs <= budget, entourés de pre/post."""
    blocks, cur, cur_len = [], [], 0
    for ln in rendered:
        ln = ln[:budget]
        if cur and cur_len + len(ln) + 1 > budget:
            blocks.append(pre + "\n".join(cur) + post)
            cur, cur_len = [], 0
        cur.append(ln)
        cur_len += len(ln) + 1
    if cur:
        blocks.append(pre + "\n".join(cur) + post)
    return blocks


def _block_values(block: dict) -> list[str]:
    """Valeurs de champ pour un bloc. Listes simples -> texte brut ; changements
    -> bloc ANSI (flèches colorées)."""
    lines = block["lines"]
    if all(kind == "text" for kind, _, _ in lines):
        return _chunk([t for _, _, t in lines], MAX_FIELD_VALUE, "", "")
    rendered = [_render(kind, up, t) for kind, up, t in lines]
    inner = MAX_FIELD_VALUE - len(FENCE_OPEN) - len(FENCE_CLOSE)
    return _chunk(rendered, inner, FENCE_OPEN, FENCE_CLOSE)


def _fields(blocks: list[dict], inline: bool) -> list[dict]:
    fields = []
    for block in blocks:
        # Listes (nouveaux champions/items) et blocs ANSI : pleine largeur. Un
        # bloc de code dans un champ inline est rendu sur ~1/3 de la largeur par
        # Discord, ce qui coupe les lignes « stat avant→après » à peu près
        # partout. Seuls les champs en texte brut peuvent tenir en colonnes.
        is_list = block["name"].startswith(("🆕", "❌"))
        is_ansi = any(kind not in ("text", "header") for kind, _, _ in block["lines"])
        for i, chunk in enumerate(_block_values(block)):
            name = block["name"] if i == 0 else f"{block['name']} (suite)"
            fields.append({"name": name[:256], "value": chunk,
                           "inline": inline and not is_list and not is_ansi})
    return fields


def send_blocks(patch: str, date: str | None, url: str, blocks: list[dict],
                source: str, inline: bool = True) -> int:
    """Publie les blocs. Renvoie le nombre de messages envoyés."""
    desc = ""
    if date:
        desc += f"📅 Sortie le **{date}**\n"
    desc += f"[📖 Notes complètes]({url})\n▲ buff  ▼ nerf  ⚪ ajustement"
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
