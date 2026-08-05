"""Diff des données de deux versions DDragon pour générer un changelog détaillé.

On compare des valeurs numériques fiables (stats de base, cooldowns, coûts,
portées, prix des items). On évite volontairement de diff les tooltips en texte
brut : ils contiennent des variables et génèrent trop de faux positifs.
"""

from __future__ import annotations

# Stats de base d'un champion -> libellé FR lisible.
CHAMP_STATS = {
    "hp": "PV",
    "hpperlevel": "PV/niv",
    "mp": "Mana",
    "mpperlevel": "Mana/niv",
    "movespeed": "Vitesse",
    "armor": "Armure",
    "armorperlevel": "Armure/niv",
    "spellblock": "RM",
    "spellblockperlevel": "RM/niv",
    "attackrange": "Portée AA",
    "hpregen": "Régén PV",
    "hpregenperlevel": "Régén PV/niv",
    "mpregen": "Régén mana",
    "mpregenperlevel": "Régén mana/niv",
    "crit": "Crit",
    "attackdamage": "AD",
    "attackdamageperlevel": "AD/niv",
    "attackspeedperlevel": "Vit. att./niv",
    "attackspeed": "Vit. att.",
}

# Champs "burn" des sorts : chaînes façon "8/7/6/5/4" faciles à comparer.
SPELL_FIELDS = {
    "cooldownBurn": "CD",
    "costBurn": "Coût",
    "rangeBurn": "Portée",
}


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


def _real_champs(data: dict) -> dict:
    """Ignore les variantes de modes de jeu (clés type 'Jade_Ahri').

    Les vrais champions de la Faille ont une clé sans underscore (ex: 'MissFortune').
    """
    return {k: v for k, v in data.items() if "_" not in k}


def diff_champions(old: dict, new: dict) -> dict:
    """Renvoie {'added': [...], 'removed': [...], 'changed': {champ: [lignes]}}."""
    old, new = _real_champs(old), _real_champs(new)
    old_keys, new_keys = set(old), set(new)
    added = sorted(new[k]["name"] for k in new_keys - old_keys)
    removed = sorted(old[k]["name"] for k in old_keys - new_keys)
    changed: dict[str, list[str]] = {}

    for key in sorted(old_keys & new_keys):
        o, n = old[key], new[key]
        lines: list[str] = []

        # Stats de base
        o_stats, n_stats = o.get("stats", {}), n.get("stats", {})
        for stat, label in CHAMP_STATS.items():
            ov, nv = o_stats.get(stat), n_stats.get(stat)
            if ov is not None and nv is not None and ov != nv:
                arrow = "🔺" if nv > ov else "🔻"
                lines.append(f"{arrow} {label} : {_fmt(ov)} → {_fmt(nv)}")

        # Sorts (Passif inclus via 'passive' n'a pas de burn, on prend spells[])
        o_spells = o.get("spells", [])
        n_spells = n.get("spells", [])
        slots = ["Q", "W", "E", "R"]
        for i in range(min(len(o_spells), len(n_spells))):
            os_, ns_ = o_spells[i], n_spells[i]
            slot = slots[i] if i < len(slots) else f"S{i}"
            for field, label in SPELL_FIELDS.items():
                ov, nv = os_.get(field), ns_.get(field)
                if ov is not None and nv is not None and ov != nv:
                    lines.append(f"• {slot} {label} : {ov} → {nv}")

        if lines:
            changed[n["name"]] = lines

    return {"added": added, "removed": removed, "changed": changed}


def diff_items(old: dict, new: dict) -> dict:
    """Diff des items : ajouts/retraits et changements de prix total."""
    def buyable(d):
        # Uniquement les items achetables, sur la Faille de l'invocateur (map 11).
        return {
            k: v for k, v in d.items()
            if v.get("gold", {}).get("purchasable")
            and v.get("gold", {}).get("total", 0) > 0
            and v.get("maps", {}).get("11")
        }

    old, new = buyable(old), buyable(new)
    old_keys, new_keys = set(old), set(new)
    added = sorted(new[k]["name"] for k in new_keys - old_keys)
    removed = sorted(old[k]["name"] for k in old_keys - new_keys)
    price: list[str] = []

    for key in old_keys & new_keys:
        ov = old[key].get("gold", {}).get("total")
        nv = new[key].get("gold", {}).get("total")
        if ov is not None and nv is not None and ov != nv:
            arrow = "🔺" if nv > ov else "🔻"
            price.append(f"{arrow} {new[key]['name']} : {ov} → {nv} po")

    return {"added": added, "removed": removed, "price": sorted(price)}
