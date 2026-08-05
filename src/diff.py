"""Diff des données DDragon entre deux versions — REPLI si le scraping échoue.

Moins complet que les notes officielles (pas de dégâts de sorts fiables) mais
100 % robuste. Produit le même format de blocs que scraper.py :
[{'name': str, 'lines': [(kind, up, text)]}] où kind ∈ buff/nerf/neutral/text,
up ∈ True/False/None. Le rendu (flèche colorée) est fait par notify.py.
"""

from __future__ import annotations

# Stats de base d'un champion -> libellé FR. Toutes : hausse = buff.
CHAMP_STATS = {
    "hp": "PV", "hpperlevel": "PV/niv", "mp": "Mana", "mpperlevel": "Mana/niv",
    "movespeed": "Vitesse", "armor": "Armure", "armorperlevel": "Armure/niv",
    "spellblock": "RM", "spellblockperlevel": "RM/niv", "attackrange": "Portée AA",
    "hpregen": "Régén PV", "hpregenperlevel": "Régén PV/niv", "mpregen": "Régén mana",
    "mpregenperlevel": "Régén mana/niv", "crit": "Crit", "attackdamage": "AD",
    "attackdamageperlevel": "AD/niv", "attackspeedperlevel": "Vit. att./niv",
    "attackspeed": "Vit. att.",
}

# Champs "burn" scalaires des sorts -> (libellé, "hausse = buff ?").
SPELL_FIELDS = {
    "cooldownBurn": ("CD", False),   # baisser un CD = buff
    "costBurn": ("Coût", False),     # baisser un coût = buff
    "rangeBurn": ("Portée", True),
}

SLOTS = ["Q", "W", "E", "R"]


def _fmt(v) -> str:
    return f"{v:.4g}" if isinstance(v, float) else str(v)


def _burn_sum(s):
    total, seen = 0.0, False
    for part in str(s).split("/"):
        try:
            total += float(part.strip()); seen = True
        except ValueError:
            pass
    return total if seen else None


def _real_champs(data: dict) -> dict:
    # Ignore les variantes de modes de jeu (clés type 'Jade_Ahri').
    return {k: v for k, v in data.items() if "_" not in k}


def _champ_lines(o: dict, n: dict) -> list[tuple]:
    lines: list[tuple] = []
    o_stats, n_stats = o.get("stats", {}), n.get("stats", {})
    for stat, label in CHAMP_STATS.items():
        ov, nv = o_stats.get(stat), n_stats.get(stat)
        if ov is not None and nv is not None and ov != nv:
            up = nv > ov
            lines.append(("buff" if up else "nerf", up, f"{label} {_fmt(ov)}→{_fmt(nv)}"))

    o_spells, n_spells = o.get("spells", []), n.get("spells", [])
    for i in range(min(len(o_spells), len(n_spells))):
        slot = SLOTS[i] if i < len(SLOTS) else f"S{i}"
        for field, (label, up_is_buff) in SPELL_FIELDS.items():
            ov, nv = o_spells[i].get(field), n_spells[i].get(field)
            if ov is not None and nv is not None and ov != nv:
                os_, ns_ = _burn_sum(ov), _burn_sum(nv)
                text = f"{slot} {label} {ov}→{nv}"
                if os_ is None or ns_ is None or os_ == ns_:
                    lines.append(("neutral", None, text))
                else:
                    up = ns_ > os_
                    lines.append(("buff" if (up == up_is_buff) else "nerf", up, text))
    return lines


def build_blocks(old_champ: dict, new_champ: dict, old_items: dict, new_items: dict) -> list[dict]:
    blocks: list[dict] = []
    oc, nc = _real_champs(old_champ), _real_champs(new_champ)
    ock, nck = set(oc), set(nc)

    added = sorted(nc[k]["name"] for k in nck - ock)
    removed = sorted(oc[k]["name"] for k in ock - nck)
    if added:
        blocks.append({"name": "🆕 Nouveaux champions", "lines": [("text", None, ", ".join(added))]})
    if removed:
        blocks.append({"name": "❌ Champions retirés", "lines": [("text", None, ", ".join(removed))]})

    for key in sorted(ock & nck):
        lines = _champ_lines(oc[key], nc[key])
        if lines:
            blocks.append({"name": nc[key]["name"], "lines": lines})

    # Items (Faille de l'invocateur uniquement).
    def buyable(d):
        return {
            k: v for k, v in d.items()
            if v.get("gold", {}).get("purchasable")
            and v.get("gold", {}).get("total", 0) > 0
            and v.get("maps", {}).get("11")
        }

    oi, ni = buyable(old_items), buyable(new_items)
    oik, nik = set(oi), set(ni)
    it_added = sorted(ni[k]["name"] for k in nik - oik)
    it_removed = sorted(oi[k]["name"] for k in oik - nik)
    if it_added:
        blocks.append({"name": "🆕 Nouveaux items", "lines": [("text", None, ", ".join(it_added))]})
    if it_removed:
        blocks.append({"name": "❌ Items retirés", "lines": [("text", None, ", ".join(it_removed))]})

    price = []
    for key in oik & nik:
        ov = oi[key].get("gold", {}).get("total")
        nv = ni[key].get("gold", {}).get("total")
        if ov is not None and nv is not None and ov != nv:
            up = nv > ov
            price.append(("nerf" if up else "buff", up, f"{ni[key]['name']} {ov}→{nv} po"))
    if price:
        blocks.append({"name": "💰 Prix des items", "lines": sorted(price, key=lambda t: t[2])})

    return blocks
