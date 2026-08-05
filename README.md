# 🩹 LoL Patch Bot

Poste automatiquement un changelog détaillé dans un salon Discord dès qu'un
nouveau patch de League of Legends sort.

- **Détection** : API officielle Data Dragon de Riot (`versions.json`), gratuite, sans clé.
- **Contenu** : diff des données parsées entre l'ancienne et la nouvelle version
  (stats de base des champions, cooldowns/coûts/portées des sorts, nouveaux/retirés
  champions & items, changements de prix), en **français**.
- **Envoi** : webhook Discord (aucun serveur à héberger).
- **Cron** : GitHub Actions, toutes les 15 min — 100 % gratuit.

## Fonctionnement

```
GitHub Actions (cron 15 min)
   └─ src/main.py
        ├─ DDragon versions.json  → nouvelle version ?
        ├─ diff champions + items (vs version précédente)
        └─ webhook Discord (embed FR)  +  maj data/state.json (commit)
```

`data/state.json` mémorise la dernière version notifiée. Au premier lancement, le
bot enregistre la version courante **sans** notifier (pour ne pas spammer un patch
déjà sorti).

## Installation (5 min)

1. **Crée le webhook Discord**
   Salon cible → *Paramètres* → *Intégrations* → *Webhooks* → *Nouveau webhook* →
   copie l'URL.

2. **Push ce dossier sur un repo GitHub** (public ou privé, peu importe).

3. **Ajoute le secret**
   Repo → *Settings* → *Secrets and variables* → *Actions* → *New repository secret*
   - Nom : `DISCORD_WEBHOOK_URL`
   - Valeur : l'URL du webhook

4. C'est tout. Le workflow tourne toutes les 15 min. Tu peux le déclencher à la main
   dans l'onglet *Actions* → *Check LoL patch* → *Run workflow*.

## Tester en local

```bash
# Aperçu sans rien envoyer (mode DRY-RUN, affiche le payload) :
python3 src/main.py --force

# Envoi réel vers ton webhook :
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python3 src/main.py --force
```

`--force` ignore le state et compare l'avant-dernière version à la dernière, pratique
pour prévisualiser le rendu d'un patch déjà sorti.

## Idées d'évolution

- Enrichir avec les vraies notes texte scrapées depuis le site officiel.
- Diff des runes / des objets légendaires détaillés.
- Passage à un vrai bot Discord avec commandes `/lastpatch`, `/champ <nom>`.
- Multi-langue / multi-serveur.
