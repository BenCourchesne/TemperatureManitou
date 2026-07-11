# Plan d'implémentation — Station météo Ecowitt + Lune/Solunaire

Document de référence à consulter avant et pendant l'implémentation.
Cases à cocher pour suivre l'avancement.

---

## Contexte

Le site Lac Manitou (`lmt.bcourchesne.com` — Firebase Hosting + Realtime
Database, code dans `index.html`) affiche aujourd'hui 4 mesures : air (véranda),
eau surface, eau 4 pieds, humidité.

Ben ajoute une station **Ecowitt GW3002 + WN32** (WN32 dans le boathouse =
future source primaire d'air/humidité, plus fiable que la véranda) qui apportera
**vent, pluie, UV, luminosité, pression**. Objectif : transformer le site en
tableau de bord météo complet, réorganisé par catégories, avec tendances, une
tuile phase de lune et un panneau solunaire (activité pêche/faune).

**Direction UX validée** (maquettes approuvées) : tuiles denses regroupées en
3 sections + tendances ; lune = tuile phase **et** panneau solunaire complet.

---

## Séquencement (2 phases)

- **Phase A — sans matériel.** Refonte UX (catégories + tendances), tuile phase
  de lune + panneau solunaire (calcul 100 % client). Les tuiles des métriques
  Ecowitt pas encore branchées affichent `—` et s'allumeront en Phase B.
- **Phase B — quand les entités Ecowitt sont dans HA.** Brancher
  vent/pluie/UV/luminosité/pression de bout en bout. ✅ **Fait et déployé**
  (voir statut ci-dessous) — seuls `airb`/`humb` (WN32) restent en attente.

---

## Statut au 2026-07-08 — Phases A + B déployées en prod

Phase A **et** Phase B sont **en production** (`firebase deploy --only
hosting` ; dernier commit `b83f8f5` sur la branche `weather-station`).

- Station Ecowitt configurée dans HA sous le nom de device **`gw3000b`**
  (unités déjà en métrique). Elle pousse **vent, rafale, direction, taux de
  pluie, cumul jour, UV, luminosité, pression** toutes les 5 min via
  `manitou_firebase`. Les tuiles s'allument, le graphique et `/daily`
  fonctionnent pour chaque mesure.
- **Backfill** de 132 lectures depuis 21 h la veille effectué à partir de
  l'historique recorder de HA (`backfill_ecowitt.py`).
- Polish frontend livré : tendance pluie « sec / taux », stats généralisées,
  alignement Solaire/Lune, nettoyage des étiquettes d'axe Y.

**Seul point bloqué** : `airb`/`humb` (température/humidité abritées du
boathouse, capteur **WN32 pas encore reçu par HA**). Placeholders prêts à
décommenter dans `home_assistant.yaml`.

**Reste faisable maintenant (sans matériel)** : — (audit responsive ≤ 480 px ✅
fait ; vérif solunaire ✅ faite). Il ne reste que `airb`/`humb` (matériel WN32).

---

## Décisions de design (UX) — validées

Mise en page (de haut en bas) :

```
En-tête (logo · Lac Manitou · LIVE · FR/EN)          [inchangé, déjà en place]
AIR & ATMOSPHÈRE      Air    · Humidité · Pression   [3 tuiles + tendances]
EAU DU LAC            Surface · 4 pieds               [2 tuiles + tendances]
CIEL & CONDITIONS     Vent · Pluie · UV · Lumino · Lune(phase)  [5 tuiles]
ACTIVITÉ LUNAIRE      panneau solunaire complet       [phase+cote+maj/min+barre 24h]
Sélecteur de mesure (pilules) + onglets période (24h…Année)
Graphique
Stats Min/Moy/Max
```

Mapping métrique → catégorie → couleur → icône Tabler :

| Métrique | Section | Couleur (var CSS) | Icône | Unité |
|---|---|---|---|---|
| Air | Air & atmo | `--air #fbbf24` | ti-temperature | °C |
| Humidité | Air & atmo | `--humidity #22d3ee` | ti-droplet | % |
| Pression | Air & atmo | `--pressure #94a3b8` | ti-gauge | hPa |
| Surface | Eau | `--surface #bae6fd`/#7dd3fc | ti-ripple | °C |
| 4 pieds | Eau | `--depth #1e40af`/#818cf8 | ti-wave-sine | °C |
| Vent | Ciel | `--wind #2dd4bf` | ti-wind | km/h (+rafale) |
| Pluie | Ciel | `--rain #38bdf8` | ti-cloud-rain | mm (+mm/h) |
| UV | Ciel | `--uv #a78bfa` | ti-sun | index |
| Luminosité | Ciel | `--solar #fb923c` | ti-brightness-up | W/m² |
| Lune | Ciel | `--moon #cbd5e1` | ti-moon | % éclairée |

Règles de tendance (flèches) :
- Températures : flèche + rouge (↑) / vert (↓) — comportement actuel conservé.
- Météo (humidité, vent, UV, luminosité) : flèche **neutre gris** (ni bon ni mauvais).
- **Pression** : mise en évidence si en baisse (bordure + texte orange) — seule
  tendance vraiment prédictive.
- **Pluie** : pas de flèche (cumul) → « sec » / « X mm/h ».

Chaîne de repli air : **WN32 boathouse → véranda → (sonde chalet #2, futur) →
sonde quai**. Le helper `val(d,'air')` implémente la priorité.

---

## Tâches — UX / Design

- [x] Confirmer les **coordonnées GPS du lac** — ✅ fait : 46.0471, -74.3739
      (lues depuis la config HA), en dur dans la constante `LAKE`.
- [x] Valider l'ordre final des tuiles dans « Ciel & conditions » — ✅ Vent,
      Pluie, UV, Luminosité, Lune (phase).
- [x] **Comportement des stats sous le graphique** — ✅ tranché et implémenté
      (2026-07-08) : **cœur fixe** (`air/surface/depth/humidity`) **+ la mesure
      météo sélectionnée** ajoutée quand elle est en mode solo. La **pluie**
      affiche un **« Total »** (somme reset-aware : pic par cycle en 24h/7j/30j,
      somme des totaux quotidiens en saison/année) au lieu de Min/Moy/Max.

## Tâches — Front End (`index.html`)

- [x] **Variables CSS couleur** — ✅ `--wind --rain --uv --solar --pressure
      --moon` (+ `--radar` ajouté depuis pour la section Prévisions).
- [x] **Sections catégorisées** — ✅ Air & atmosphère / Eau du lac / Ciel &
      conditions, chacune avec en-tête de section.
- [x] **Nouvelles tuiles** — ✅ Pression, Vent, Pluie, UV, Luminosité, Lune
      toutes présentes, affichent `—` tant que Phase B n'a pas de données.
- [x] **Tendances généralisées** — ✅ `trendLabel` gère les unités par mesure,
      couleurs neutres pour la météo, mise en évidence pression en baisse.
- [x] **Tendance pluie — cas spécial** — ✅ fait (2026-07-08) : la tuile Pluie
      affiche **« sec »** si `rday ≈ 0`, sinon le taux/cumul, au lieu de la
      flèche générique ↑/↓ inadaptée à un cumul croissant.
- [x] **Sélecteur de mesure du graphique** — ✅ fait, mais avec des **cases à
      cocher exclusives** (pas des pilules comme prévu à l'origine) : logique
      généralisée `SOLO`/`seriesVisible` qui bascule axe Y + unité. Fonctionne,
      juste un choix visuel différent de l'esquisse initiale.
- [x] **`fetchData`** — ✅ **complet** : le brut (24h) et `/daily` transportent
      tous les champs (spread `...obj[k]`) ; le bucket horaire (7j/30j) agrège
      maintenant aussi pression/vent/pluie/UV/luminosité (moyenne, via `val()`
      généralisé + `RAW_PROP`), plus seulement air/surface/depth/airv/hum.
      Bloquant Phase B résolu.
- [x] **Étiquettes d'axe Y propres** — ✅ fait (2026-07-08) : helper `axisNum`
      qui supprime le bruit flottant des ticks (ex. `970.4000000000001 hPa` →
      `970.4`) sans imposer de décimales fixes.
- [x] **Tuile phase de lune** — ✅ icône SVG dynamique (voir section Lune).
- [x] **Panneau solunaire** — ✅ accordéon (voir section Lune).
- [x] **i18n FR/EN** — ✅ tous les libellés mesures/phases/majeures-mineures/
      lever-coucher présents dans les deux langues.
- [x] **Responsive ≤480px** : ✅ audité (2026-07-08) sur 320/360/375/414/480px,
      accordéons ouverts. Aucun débordement horizontal de page. Corrigés :
      onglets de période (`min-width:0` pour que `flex:1` rétrécisse), toggle
      °C/°F qui débordait des tuiles Eau (`.cards-2 .card-temp` 1.7rem + gap
      réduit — spécificité requise car le bloc media est AVANT les règles de
      base dans le CSS), et largeur des tuiles prévisions (min-width 38→34 pour
      tenir 7 jours à 360px).

## Tâches — Lune + Solunaire (calcul 100 % client) — ✅ TOUT FAIT

- [x] SunCalc chargé depuis cdnjs.
- [x] Constante `LAKE = { lat: 46.0471, lon: -74.3739 }`.
- [x] Tuile phase : icône SVG (croissant/gibbeuse) générée depuis la fraction
      exacte + %.
- [x] Solunaire complet : majeures (transit/anti-transit ±1h), mineures
      (lever/coucher lune ±0.5h), cote ★, barre 24h, lever/coucher soleil
      (déplacés dans la tuile Solaire) et lune (dans la tuile Lune).
      Affiché en **accordéon** au clic sur la tuile Lune (badge Détails/
      Masquer, clavier-accessible), pas dans le flux par défaut.
- [x] Vérifier les heures contre une source en ligne — ✅ fait (2026-07-08),
      comparé à **USNO** (aa.usno.navy.mil, coordonnées exactes) et
      sunrise-sunset.org pour le soleil :
  - **Soleil** (lever/coucher/transit) : ~1 min d'écart → excellent.
  - **Lever de lune** + période mineure associée : ~2 min → excellent.
  - **Transit lune** (→ majeures) et **coucher de lune** (→ 2ᵉ mineure) :
    ~12–17 min de retard vs USNO. C'est le plafond du modèle lunaire de SunCalc
    (une recherche de transit à la minute donne toujours ~12 min d'écart, donc
    ce n'est pas la résolution ni un bug de code). **Acceptable** pour un
    tableau solunaire (fenêtres ±1 h = heuristique). Aucun bug de fuseau.
- [x] **Nom de phase lunaire** — ✅ corrigé (2026-07-08) : `round(phase*8)`
      donnait à « dernier quartier » une tranche de ±1.85 j (affiché ~1,5 j après
      le vrai quartier). Remplacé par un nommage à fenêtre étroite (~±0.6 j) pour
      les 4 phases principales, croissant/gibbeuse le reste du temps. Ex.
      40 % décroissant = « Dernier croissant » (et non « Dernier quartier »).

## Tâches — Firebase

- [x] **Modèle de données** `readings/{ms}` — ✅ champs `wind, gust, wdir,
      rrate, rday, uv, solar, press` écrits en prod. ✅ **`airb, humb` branchés
      ET VÉRIFIÉS EN PROD (2026-07-10)** — WN32 reçu et enregistré sur `gw3000b`
      (id `0x9E`, a pris le rôle « outdoor » principal, devant le T/H intégré au
      WS69). Entités confirmées : `sensor.gw3000b_outdoor_temperature` /
      `sensor.gw3000b_humidity`. Piège rencontré : le placeholder `<WN32>` du
      commentaire d'origine avait été laissé tel quel après le décommenter (donc
      `sensor.<WN32>_temperature` — entité inexistante, `num()` renvoyait `null`
      silencieusement, pas d'erreur visible) — corrigé en remplaçant par les
      vrais noms d'entité. Confirmé dans `/readings` : `airb: 26.6, humb: 51`,
      cohérent avec la lecture native du gateway (~26.8 °C / 53 %). Rétro-compat
      OK (absents gérés côté front pour l'historique pré-WN32).
- [x] **`/daily/{ms}`** — ✅ agrégats avec **règles par métrique** implémentés :
  - moyenne : temp, pression, UV, luminosité, humidité (+ `airb`/`humb` ✅ branchés)
  - **max** : pluie cumul (`rday`) — le max du jour = total du jour
  - **moyenne + max** : vent (`wind` moy, `gustmax` = rafale max du jour)
- [x] Étendre `firebase_put_daily` + le script (selectattr-guarded, comme
      `airv/hum`, avec `rejectattr('none')` pour les `null` du macro `num()`) — ✅.
- [x] Reconstruire `/daily` — ✅ automatique : le script auto-réparant recalcule
      les 10 derniers jours manquants à chaque run.
- [x] Règles RTDB : inchangées — ✅ rien à faire (confirmé).

## Tâches — Home Assistant (`home_assistant.yaml`) — Phase B

- [x] Configurer l'**intégration Ecowitt** — ✅ déjà en place (device HA
      `gw3000b`), unités métriques confirmées.
- [x] **Noms d'entités** — ✅ capturés : `sensor.gw3000b_wind_speed`,
      `_wind_gust`, `_wind_direction`, `_rain_rate`, `_daily_rain`, `_uv_index`,
      `_solar_radiation`, `_relative_pressure`. WN32 (2026-07-10) : id `0x9E`,
      remplace le T/H intégré du WS69 comme capteur « outdoor » principal du
      gateway → `sensor.gw3000b_outdoor_temperature` / `_humidity` (⏳ à
      confirmer dans Réglages → Appareils → `gw3000b` avant le premier déploiement
      — le macro `num()` étant null-safe, un mauvais nom d'entité échouerait
      silencieusement en `null` plutôt qu'en erreur).
- [x] `manitou_firebase` payload — ✅ **10 champs** ajoutés via macro `num()`
      null-safe, `airb`/`humb` (WN32) branchés (2026-07-10).
- [x] Helper `val('air')` priorité WN32 → véranda → quai — ✅ déjà codé
      (`airb ?? airv ?? air`) ; s'activera dès que `airb` sera écrit.
- [ ] **NE PAS** intégrer `sensor.chalet_*` (Honeywell) pour l'instant —
      l'analyse a montré qu'à l'emplacement #1 la sonde est amortie par la masse
      du mur (biais opposé à la véranda, pas meilleure). À réévaluer après
      déplacement au #2 (nord, déportée du mur) + nouvelle comparaison.

## Tâches — Backfill des données

- [x] **Véranda/humidité** : déjà fait (`backfill_veranda.py`).
- [x] **Ecowitt** : ✅ fait (2026-07-08) — contrairement à la note initiale, un
      backfill EST possible via l'**historique recorder de HA** (~10 j de
      rétention). `backfill_ecowitt.py` (réutilise les helpers/secrets de
      `backfill_veranda.py`, idempotent, mode dry-run par défaut) a rempli 132
      lectures depuis 21 h la veille. Extensible : baisser `START_LOCAL` pour
      remonter plus loin dans la rétention.
- [ ] **Optionnel — sonde chalet** : si un jour on l'intègre après déplacement,
      backfill via le même pattern (`/api/history` HA → PATCH `readings`), en
      respectant la rétention recorder (~10 j).

---

## Vérification

**Phase A** : `firebase hosting:channel:deploy rtdb-test` puis vérifier **en
navigation privée** (le cache Hosting sert l'ancienne version — Ctrl+Shift+R
insuffisant) :
- 3 sections dans le bon ordre, tendances correctes, tuiles Ecowitt à `—`.
- Tuile phase de lune plausible ; panneau solunaire (heures maj/min comparées à
  une table en ligne).
- Bascule de mesure sur le graphique (pilules) OK ; responsive/mobile OK.
- Puis `firebase deploy --only hosting` (live).

**Phase B** : après config Ecowitt, forcer une écriture HA, vérifier via
PowerShell que `readings` contient les nouveaux champs, que les tuiles
s'allument, et que graphique + `/daily` marchent pour chaque mesure.

---

## Bugs connus

- [x] **Radar : le scroll de la souris déclenche le zoom de la carte au lieu du
      scroll de la page.** ✅ fait (fix rapide) — `panel.scrollIntoView(
      {behavior:'smooth', block:'center'})` appelé à l'ouverture des deux
      accordéons (Radar et Lune), centre le viewport automatiquement, plus
      besoin de scroller manuellement dessus. Le fix plus robuste (calque
      « cliquez pour interagir » bloquant le scroll résiduel) reste optionnel
      si le souci revient malgré l'auto-scroll.

---

## Tâches — Idées futures (non implémentées, à planifier)

Backlog capturé le 2026-07-07, rien de ceci n'est implémenté — à détailler et
prioriser avant de commencer.

- [x] **Tuile Lune → icône de phase + %** : ✅ fait (2026-07-07) — icône SVG de
      croissant/gibbeuse générée dynamiquement depuis la fraction éclairée
      exacte (formule à arcs elliptiques), pas un set statique de 30 images.
- [x] **Panneau solunaire caché par défaut** : ✅ fait (2026-07-07) — implémenté
      en **accordéon** (pas modal) : clic sur la tuile Lune (badge « Détails ▾ »,
      bordure teal, clavier-accessible) révèle le panneau juste en dessous dans
      le flux de la page ; reclique pour le masquer. Moonrise déplacé de
      l'ancien panneau vers la tuile Lune elle-même.
- [x] **Aligner les séparateurs Solaire/Lune** : ✅ fait (2026-07-08). Cause
      identifiée en preview : le bloc-valeur Solaire fait 2 lignes (l'unité
      `W/m²` passe sous le chiffre) contre 1 ligne pour la Lune, décalant la
      rangée Lever soleil de ~25 px sous Lever lune. Fix : `min-height: 3.4rem`
      sur `.card-solar .card-value-row, .card-moon .card-value-row` → rangées
      alignées (vérifié à 2 px près, desktop ; en mobile les tuiles s'empilent,
      pas d'adjacence).
- [x] **Renommer la section graphique** : ✅ fait (2026-07-07) — renommé en
      « Historique des données » / « Historical data ».
- [ ] **Photo horaire (webcam)** : capturer une photo à chaque heure et l'afficher
      sur le site (dernière photo, ou petite galerie/timelapse).

  **Matériel choisi (2026-07-10)** : **Reolink RLC-510A**, objectif **4 mm**
  (PAS le 2.8 mm fisheye — le 4 mm est plus serré/plat, plus facile à cadrer pour
  **exclure les bateaux** du champ), PoE, IP66 (extérieur, hiver). ~**85 $ CAD +
  tx** (~98 $ tout inclus). ONVIF/RTSP natif → s'intègre directement à HA.
  Monter **haut, légèrement vers le haut** (eau + horizon + ciel) pour la valeur
  météo/ambiance sans montrer le quai ni les bateaux (vie privée/sécurité).
  - Rejeté : **ESP32-CAM** (OV2640 2 MP, mauvaise plage dynamique → massacre les
    levers de soleil dans la brume ; pas étanche ; WiFi). Bon pour le thème DIY,
    mauvais outil pour la photo « hero ».

  **Alimentation — ⚠️ plus de port PoE libre.** Le switch **TP-Link 8 ports
  (4 PoE)** du boathouse est saturé côté PoE : 2 caméras sécurité + PTP Ubiquiti
  + AP WiFi Ubiquiti + ESP32-POE (+ base Arlo, non-PoE, sur port data). Certains
  Ubiquiti sont déjà sur leur propre injecteur.
  - **Solution** : **injecteur PoE actif autonome** — TP-Link **TL-PoE160S**
    (802.3af/at, gigabit, ~25 $). Il se branche sur un **port data ordinaire**
    (pas un port PoE) + une prise murale → **n'utilise aucun port PoE ni le
    budget PoE du switch**.
  - ⚠️ **NE PAS réutiliser un injecteur Ubiquiti passif 24 V/48 V** : mauvais
    standard, **endommagerait** la Reolink (802.3af). Injecteur **actif**
    obligatoire.
  - ⏳ **À VÉRIFIER physiquement au boathouse** : reste-t-il un **port data
    libre** sur le switch 8 ports ? (analyse : ~6/8 ports utilisés → 1–2 libres
    probables, mais à confirmer sur place — switch non-managé, invérifiable à
    distance). Si tout est plein : ajouter un petit switch 5 ports (~20 $) pour
    gagner des ports, puis brancher l'injecteur dessus.
  - Coût total estimé : cam ~98 $ + injecteur ~28 $ ≈ **126 $ CAD**.

  **Pipeline (option A, sans Cloud Functions, cohérent avec l'archi actuelle)** :
  1. HA récupère la cam via l'intégration **ONVIF / Generic Camera** (URL RTSP).
  2. Automation horaire → service **`camera.snapshot`** (JPEG).
  3. HA **upload le JPEG vers Firebase Storage** (auth compte `ha-writer`, même
     token que `manitou_firebase`). Storage, PAS RTDB (image trop grosse).
  4. Le front affiche la **dernière photo** dans une tuile « conditions
     actuelles » (à côté des tuiles capteurs).
  - À définir : activer Firebase Storage (Spark = 5 Go gratuits), règles de
    sécurité Storage (lecture publique de la dernière photo), **rétention**
    (combien de photos garder — écraser une seule « latest.jpg » vs
    galerie/timelapse horodatée).

  **Prérequis avant de commencer** : (1) commander la cam **variante 4 mm** +
  injecteur actif ; (2) confirmer un port data libre sur le switch ; (3) capturer
  l'URL RTSP + l'ajouter à HA.
- [ ] **Navigation temporelle sur le graphique** : pouvoir choisir un jour, un
      mois ou une année précis dans le passé (pas seulement des fenêtres
      glissantes 24h/7j/30j/Saison/Année) — un vrai sélecteur de date pour
      « remonter dans le temps ». Implique une UI de sélection de date +
      requêtes RTDB par plage arbitraire (déjà possible via `orderBy`+
      `startAt`/`endAt` sur la clé timestamp).
- [x] **Radar météo embarqué** : ✅ fait (2026-07-07) — nouvelle section
      « Prévisions » (entre Ciel & conditions et les onglets de période),
      positionnée délibérément comme catégorie « ce qui s'en vient » (externe/
      prédictif) distincte des mesures propres au site. Tuile Radar en
      accordéon (même pattern que la Lune), carte Windy centrée sur le lac,
      **iframe chargée seulement à la première ouverture** (économie de bande
      passante). `.forecast-row` (flex, pas grille) déjà dimensionné pour
      accueillir les tuiles de prévisions 7 jours à côté, sans réorganisation.
- [x] **Prévisions météo 7 jours (forecast)** : ✅ fait (2026-07-08). Source =
      **Environnement Canada** via `api.weather.gc.ca` (collection
      `citypageweather-realtime`, site le plus proche = Sainte-Agathe `qc-33`,
      CORS OK, payload bilingue). Carte « Prévisions 7 jours » à droite du radar
      dans `.forecast-row` (passe sous le radar sur petit écran) : 7 tuiles jour
      avec icône (mapping code EC → Tabler, vérifié contre le CSV officiel),
      max (rouge) / min (bleu) empilés, résumé en infobulle, attribution EC.
      Rafraîchi chaque heure ; échec réseau = carte masquée silencieusement.

---

## Questions ouvertes / à confirmer

- ✅ ~~Coordonnées GPS exactes du lac~~ — résolu : 46.0471, -74.3739.
- ✅ ~~Noms d'entités Ecowitt~~ — résolu : device `gw3000b` (WN32 à capturer à
  sa réception pour `airb`/`humb`).
- ✅ ~~Stats du graphique mono-mesure~~ — résolu : cœur fixe + mesure sélectionnée.
- ✅ ~~WiFi boathouse = même sous-réseau que HA ?~~ — résolu : la station pousse
  bien les données, le push local fonctionne.
- ⏳ **WN32** : à recevoir dans HA pour brancher `airb`/`humb`.
- ⏳ **Sonde chalet** : à réévaluer après déplacement au #2.
- ✅ ~~Responsive ≤ 480 px~~ — audité 320–480px, débordements corrigés.
- ✅ ~~Vérif solunaire~~ — faite (USNO) : soleil/lever-lune ~1–2 min, transit/
  coucher-lune ~12–17 min (plafond SunCalc, acceptable). Nom de phase corrigé.
