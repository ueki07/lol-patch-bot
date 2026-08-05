"""Point d'entrée : détecte un nouveau patch et poste le changelog sur Discord.

Logique :
  1. Lit la dernière version connue dans data/state.json.
  2. Interroge DDragon pour la version la plus récente.
  3. Si identique -> rien à faire.
  4. Sinon -> diff des champions et items entre les deux versions, envoi Discord,
     puis mise à jour de state.json.

Au tout premier lancement (state vide), on ne poste rien : on enregistre juste la
version courante pour éviter de spammer un patch déjà sorti.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import ddragon
import diff
import notify

STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "state.json")


def load_state() -> dict:
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"version": None}


def save_state(version: str) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"version": version}, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> None:
    force = "--force" in sys.argv
    state = load_state()
    known = state.get("version")

    versions = ddragon.latest_versions()
    latest = versions[0]
    print(f"Version connue : {known} | dernière DDragon : {latest}")

    if latest == known and not force:
        print("Pas de nouveau patch.")
        return

    if known is None and not force:
        print("Premier lancement : on enregistre la version sans notifier.")
        save_state(latest)
        return

    # Version de comparaison : la précédente connue. En --force (aperçu) où le state
    # vaut déjà la dernière version, on compare à l'avant-dernière de la liste.
    fallback = versions[1] if len(versions) > 1 else latest
    prev = known if (known and known != latest) else fallback
    print(f"Nouveau patch détecté : {prev} → {latest}")

    champ_diff = diff.diff_champions(
        ddragon.champions_full(prev), ddragon.champions_full(latest)
    )
    item_diff = diff.diff_items(ddragon.items(prev), ddragon.items(latest))
    date = ddragon.patch_date(latest)

    notify.send_patch(latest, prev, champ_diff, item_diff, date=date)
    save_state(latest)
    print("Notification envoyée et state mis à jour.")


if __name__ == "__main__":
    main()
