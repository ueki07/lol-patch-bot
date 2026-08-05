"""Diff des données de deux versions DDragon pour générer un changelog détaillé.

On compare des valeurs numériques fiables (stats de base, cooldowns, coûts,
portées, valeurs d'effets de sorts, prix des items). On évite volontairement de
diff les tooltips en texte brut : ils contiennent des variables et génèrent trop
de faux positifs.

Chaque changement est classé en 'buff' / 'nerf' / 'neutral' pour le rendu en
couleur (vert / rouge / gris). Un buff n'est pas "la valeur monte" : baisser un
cooldown ou un coût est un buff. Certains changements (effets de sorts) n'ont pas
de sens directionnel connu -> 'neutral'.
"""

from __future__ import annotations

# Stats de base d'un champion -> (libellé FR, "une hausse est-elle un buff ?").
# Toutes les stats de base : plus c'est haut, mieux c'est.
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

# Champs "burn" scalaires des sorts -> (libellé, "hausse = buff ?").
# CD et coût : baisser = buff. Portée : monter = buff.
SPELL_FIELDS = {
    "cooldownBurn": ("CD", False),
    "costBurn": ("Coût", False),
    "rangeBurn": ("Portée", True),
}

SLOTS = ["Q", "W", "E", "R"]


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


def _burn_sum(s) -> float | None:
    """Somme numérique d'une chaîne 'burn' type '8/7/6/5/4'. None si non numérique."""
    total, seen = 0.0, False
    for part in str(s).split("/"):
        try:
            total += float(part.strip())
            seen = True
        except ValueError:
            pass
    return total if seen else None


def _kind(old_val, new_val, up_is_buff: bool) -> str:
    """Classe un changement numérique en buff / nerf / neutral."""
    o, n = _burn_sum(old_val), _burn_sum(new_val)
    if o is None or n is None or o == n:
        return "neutral"
    higher = n > o
    return "buff" if higher == up_is_buff else "nerf"


def _real_champs(data: dict) -> dict:
    """Ignore les variantes de modes de jeu (clés type 'Jade_Ahri').

    Les vrais champions de la Faille ont une clé sans underscore (ex: 'MissFortune').
    """
    return {k: v for k, v in data.items() if "_" not in k}


def diff_champions(old: dict, new: dict) -> dict:
    """Renvoie {'added': [...], 'removed': [...], 'changed': {champ: [(kind, texte)]}}."""
    old, new = _real_champs(old), _real_champs(new)
    old_keys, new_keys = set(old), set(new)
    added = sorted(new[k]["name"] for k in new_keys - old_keys)
    removed = sorted(old[k]["name"] for k in old_keys - new_keys)
    changed: dict[str, list[tuple[str, str]]] = {}

    for key in sorted(old_keys & new_keys):
        o, n = old[key], new[key]
        lines: list[tuple[str, str]] = []

        # Stats de base (hausse = buff).
        o_stats, n_stats = o.get("stats", {}), n.get("stats", {})
        for stat, label in CHAMP_STATS.items():
            ov, nv = o_stats.get(stat), n_stats.get(stat)
            if ov is not None and nv is not None and ov != nv:
                kind = "buff" if nv > ov else "nerf"
                lines.append((kind, f"{label} {_fmt(ov)}→{_fmt(nv)}"))

        # Sorts : CD / coût / portée + valeurs d'effets (effectBurn).
        o_spells, n_spells = o.get("spells", []), n.get("spells", [])
        for i in range(min(len(o_spells), len(n_spells))):
            os_, ns_ = o_spells[i], n_spells[i]
            slot = SLOTS[i] if i < len(SLOTS) else f"S{i}"

            for field, (label, up_is_buff) in SPELL_FIELDS.items():
                ov, nv = os_.get(field), ns_.get(field)
                if ov is not None and nv is not None and ov != nv:
                    lines.append((_kind(ov, nv, up_is_buff), f"{slot} {label} {ov}→{nv}"))

            # NB : on ne diff PAS effectBurn (dégâts/soins des sorts). Riot y migre
            # régulièrement des valeurs vers d'autres champs, ce qui produit de faux
            # « →0 » massifs. Ces changements-là restent couverts par les notes
            # officielles (lien dans l'embed).

        if lines:
            changed[n["name"]] = lines

    return {"added": added, "removed": removed, "changed": changed}


def diff_items(old: dict, new: dict) -> dict:
    """Diff des items : ajouts/retraits et changements de prix total (baisse = buff)."""
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
    price: list[tuple[str, str]] = []

    for key in old_keys & new_keys:
        ov = old[key].get("gold", {}).get("total")
        nv = new[key].get("gold", {}).get("total")
        if ov is not None and nv is not None and ov != nv:
            kind = "buff" if nv < ov else "nerf"  # moins cher = buff
            price.append((kind, f"{new[key]['name']} {ov}→{nv} po"))

    price.sort(key=lambda t: t[1])
    return {"added": added, "removed": removed, "price": price}
