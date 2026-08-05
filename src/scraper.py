"""Scraping des notes officielles FR pour un changelog complet.

Les notes de patch Riot ont une structure HTML régulière :
  <h3 class="change-title">Nom</h3>              -> un bloc (champion, item, système)
    <h4 class="change-detail-title">Section</h4> -> sous-section (Stats de base, sort…)
      <li><strong>Attribut</strong> : ancien ⇒ <strong>nouveau</strong></li>

On en extrait chaque changement, on déduit buff / nerf / neutre à partir des
valeurs (Riot n'expose pas ce sens dans le HTML), et on renvoie des blocs prêts à
afficher. C'est la source la plus complète (champions, sorts, items, runes, ARAM,
jungle, corrections). Le diff DDragon sert de repli si le scraping casse.
"""

from __future__ import annotations

import html
import re
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# Attributs où *baisser* est un buff (cooldowns, coûts). Sinon monter = buff.
LOWER_BETTER = ("coût", "récupération", "recharge", "délai")

DOT = {"buff": "🟢", "nerf": "🔴", "neutral": "⚪"}


def notes_url(version: str, year: int | None) -> str:
    """URL des notes FR. Le numéro marketing est basé sur l'année (26.xx en 2026),
    alors que DDragon utilise 16.xx : on dérive donc le major depuis l'année."""
    parts = version.split(".")
    minor = parts[1] if len(parts) > 1 else "0"
    major = (year % 100) if year else (int(parts[0]) + 10)
    return (
        "https://www.leagueoflegends.com/fr-fr/news/game-updates/"
        f"league-of-legends-patch-{major}-{minor}-notes"
    )


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def _clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


def _num(s: str) -> float | None:
    m = re.search(r"-?\d+(?:[.,]\d+)?", s)
    return float(m.group().replace(",", ".")) if m else None


def _classify(attr: str, old: str, new: str) -> tuple[str, str]:
    """Renvoie (kind, arrow). kind ∈ buff/nerf/neutral, arrow ∈ 🔺/🔻/''."""
    o, n = _num(old), _num(new)
    scaling = "/" in old or "/" in new  # valeurs par rang -> sens ambigu
    if o is None or n is None or o == n or scaling:
        return "neutral", ""
    lower_better = any(k in attr.lower() for k in LOWER_BETTER)
    kind = "buff" if ((n > o) != lower_better) else "nerf"
    return kind, ("🔺" if n > o else "🔻")


def _block_name(seg: str) -> str:
    # seg commence juste après 'class="change-title"' : ' id="patch-x"><a>Nom</a></h3>…'
    head = seg[: seg.find("</h3>")] if "</h3>" in seg[:600] else seg[:200]
    head = head[head.find(">") + 1:]  # retire la fin de la balise <h3 ...>
    return _clean(head)


def parse(html_text: str) -> list[dict]:
    """Renvoie [{'name': str, 'lines': [str]}] — lignes prêtes à afficher.

    Chaque ligne est soit un sous-titre en gras (**Section**), soit un changement
    'pastille+flèche attribut ancien→nouveau'.
    """
    blocks: list[dict] = []
    for seg in re.split(r'class="change-title"', html_text)[1:]:
        name = _block_name(seg)
        lines: list[str] = []
        section: str | None = None
        section_emitted = False

        for m in re.finditer(
            r'class="change-detail-title[^"]*">(.*?)</h4>|<li>(.*?)</li>', seg, re.S
        ):
            if m.group(1) is not None:
                section = _clean(m.group(1))
                section_emitted = False
                continue

            txt = _clean(m.group(2))
            if not txt:
                continue

            if "⇒" in txt:
                left, right = txt.split("⇒", 1)
                if ":" in left:
                    attr, old = (p.strip() for p in left.split(":", 1))
                else:
                    attr, old = left.strip(), ""
                new = right.strip()
                kind, arrow = _classify(attr, old, new)
                sep = "→" if old else ""
                line = f"{DOT[kind]}{arrow} {attr} {old}{sep}{new}".strip()
            else:
                # Ligne sans valeur (bugfix, changement de texte) : neutre.
                if section is None or len(txt) > 300:
                    continue
                line = f"{DOT['neutral']} {txt}"

            if section and not section_emitted:
                lines.append(f"**{section}**")
                section_emitted = True
            lines.append(line)

        if any(not ln.startswith("**") for ln in lines):
            blocks.append({"name": name, "lines": lines})

    return blocks
