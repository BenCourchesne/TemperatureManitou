# Rattrapage de la panne du quai et modèle du lac (sept.–oct. 2026)

Scripts utilisés après la panne du lien NanoBeam (2026-09-18 → 2026-10-22) et le
débranchement du Pi (nuit du 22 au 23 oct.). Contexte et suivi : `PLAN.md`,
section « Suites de la panne du quai ».

**Les données ne sont pas dans le dépôt.** Les scripts lisent et écrivent dans
`D:\Claude desktop\ESPHome\recup\` (variable `HERE`) : fichiers de la carte SD
du GW3000 (`gw3000\*.csv`), `esp32.jsonl` du téléphone collecteur, instantané
`readings_all.json` de Firebase.

Tous les scripts d'écriture sont en **aperçu par défaut**. Avec `--ecrire`, ils
demandent le mot de passe du compte Firebase `ha-writer` (jamais stocké).

| Script | Rôle |
|---|---|
| `backfill.py` | Météo de la panne depuis la SD du GW3000 (horloge remise au 2024-12-31 à chaque reboot, recalée par midi solaire + pression EC Mont-Tremblant) + sondes du téléphone → `/readings` et `/daily`. **Déjà écrit — ne pas relancer.** |
| `backfill_nuit.py` | Météo de la nuit du 22-23 oct. (SD bien datée) + nettoyage du `/daily` du 22 oct. **Déjà écrit.** |
| `estime_lac.py` | Estimation surface / 4 pieds des jours sans mesures → `/daily` avec `est: 1`. **Ré-exécutable** : recale le modèle sur toutes les données et réécrit les mêmes jours. Paramètres du dernier calage : `estime_lac_params.json`. |
| `modele_variantes.py` | Comparaison air seul / air + soleil / + humidité, en validation croisée (trous d'été cachés + vraies heures d'automne cachées). |
| `modele_horaire.py` | Validation du modèle à pas de 24 h glissant (celui utilisé en production). |
| `modele_lac.py`, `modele_vent.py`, `estime_panne.py` | Premières versions (pas journalier, test du vent) — historique du raisonnement. |

## Revoir le modèle (avec plus d'historique d'automne)

1. Rafraîchir l'instantané :
   `curl -o "D:\Claude desktop\ESPHome\recup\readings_all.json" https://lac-manitou-temperatures-d284a-default-rtdb.firebaseio.com/readings.json`
2. `python modele_variantes.py` — vérifier quelle variante gagne, idéalement en
   ajoutant des trous d'automne cachés.
3. `python estime_lac.py` (aperçu), comparer avec `estime_lac_params.json`, puis
   `python estime_lac.py --ecrire`.
