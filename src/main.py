"""Point d'entrée : détecte un nouveau patch et poste le changelog sur Discord.

  1. Lit la dernière version connue (data/state.json).
  2. Interroge DDragon pour la version la plus récente.
  3. Si identique -> rien à faire.
  4. Sinon -> scrape les notes officielles (changelog complet) ; si ça échoue,
     repli sur un diff des données DDragon. Envoi Discord, puis maj du state.

Au premier lancement (state vide), on n'envoie rien : on enregistre juste la
version courante pour ne pas re-notifier un patch déjà sorti.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import ddragon
import diff
import notify
import scraper

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
    known = load_state().get("version")

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

    # Date + numéro marketing du patch (26.xx en 2026, basé sur l'année).
    dt = ddragon.patch_datetime(latest)
    date_str = ddragon.format_date_fr(dt) if dt else None
    year = dt.year if dt else None
    minor = latest.split(".")[1] if "." in latest else "0"
    major = (year % 100) if year else int(latest.split(".")[0]) + 10
    patch = f"{major}.{minor}"
    url = scraper.notes_url(latest, year)

    # Mode par défaut : résumé DDragon concis (stats de base + CD/coût/portée des
    # sorts + nouveaux/retirés + prix des items) — l'essentiel, lisible en un coup
    # d'œil. Mode --detailed : changelog complet scrapé depuis les notes officielles.
    detailed = "--detailed" in sys.argv or os.environ.get("DETAILED") == "1"

    if detailed:
        try:
            blocks = scraper.parse(scraper.fetch(url))
            print(f"Scraping OK : {len(blocks)} blocs.")
        except Exception as e:  # noqa: BLE001
            print(f"Scraping échoué ({e}). Repli sur le résumé DDragon.")
            detailed = False

    if not detailed:
        prev = known if (known and known != latest) else (
            versions[1] if len(versions) > 1 else latest)
        blocks = diff.build_blocks(
            ddragon.champions_full(prev), ddragon.champions_full(latest),
            ddragon.items(prev), ddragon.items(latest),
        )

    # Résumé -> colonnes compactes (inline) ; détaillé -> pleine largeur.
    n = notify.send_blocks(patch, date_str, url, blocks, "ok", inline=not detailed)
    print(f"{n} message(s) envoyé(s) [{'détaillé' if detailed else 'résumé'}].")
    save_state(latest)


if __name__ == "__main__":
    main()
