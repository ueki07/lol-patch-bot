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


def _burn_mean(s):
    """Moyenne des rangs d'une chaîne "burn" ("35/40/45" -> 40), ou None.

    On compare des moyennes et non des sommes : un sort peut passer d'un coût
    plat ("30") à un coût par rang ("46/42/38/34/30"). Sommer donnerait 30 vs
    190 et conclurait au nerf pour une raison fausse ; pire, "60/55/50/45/40"
    -> "50" serait annoncé buff. La moyenne reste comparable quel que soit le
    nombre de rangs, et coïncide avec la somme quand il ne change pas.
    """
    vals = []
    for part in str(s).split("/"):
        try:
            vals.append(float(part.strip()))
        except ValueError:
            pass
    return sum(vals) / len(vals) if vals else None


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
                os_, ns_ = _burn_mean(ov), _burn_mean(nv)
                text = f"{slot} {label} {ov}→{nv}"
                if os_ is None or ns_ is None or os_ == ns_:
                    lines.append(("neutral", None, text))
                else:
                    up = ns_ > os_
                    lines.append(("buff" if (up == up_is_buff) else "nerf", up, text))
    return lines


def _added_removed(old: dict, new: dict) -> tuple[list[str], list[str]]:
    """Noms ajoutés / retirés, en ignorant les simples renumérotations d'ID.

    Riot réattribue parfois l'ID d'une entrée sans rien changer d'autre (patch
    26.17 : « Lame tempête » passe de l'id 3097 à 3095). Comparer les clés seules
    annonce alors le même nom en nouveauté ET en suppression. On écarte donc les
    noms qui apparaissent des deux côtés : ce n'est pas un changement de jeu.
    """
    ok, nk = set(old), set(new)
    added = {new[k]["name"] for k in nk - ok}
    removed = {old[k]["name"] for k in ok - nk}
    both = added & removed
    return sorted(added - both), sorted(removed - both)


def build_blocks(old_champ: dict, new_champ: dict, old_items: dict, new_items: dict) -> list[dict]:
    blocks: list[dict] = []
    oc, nc = _real_champs(old_champ), _real_champs(new_champ)
    ock, nck = set(oc), set(nc)

    added, removed = _added_removed(oc, nc)
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
    it_added, it_removed = _added_removed(oi, ni)
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
