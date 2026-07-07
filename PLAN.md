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
  vent/pluie/UV/luminosité/pression de bout en bout. **Bloqué** sur les noms
  d'entités HA (à fournir après config de l'intégration Ecowitt).

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

- [ ] Confirmer les **coordonnées GPS du lac** (lat/lon) pour lune/solunaire —
      lisibles depuis la config HA (`latitude`/`longitude`) ou à coder en dur.
- [ ] Valider l'ordre final des tuiles dans « Ciel & conditions ».
- [ ] Décider du comportement des stats sous le graphique quand une seule mesure
      est affichée (garder les 4 principales vs stats de la mesure choisie).

## Tâches — Front End (`index.html`)

Réutiliser l'existant : helper `val(d,key)`, cartes `.card-*`, `renderStats`,
`trendLabel`, i18n `i18n.fr/.en`, logique `humMode` de `updateUI`.

- [ ] **Variables CSS couleur** : ajouter `--wind --rain --uv --solar
      --pressure --moon` (comme `--humidity`).
- [ ] **Sections catégorisées** : remplacer la grille `.cards` unique par
      3 blocs avec en-têtes de section (Air & atmosphère / Eau du lac / Ciel &
      conditions).
- [ ] **Nouvelles tuiles** : Pression, Vent, Pluie, UV, Luminosité, Lune(phase)
      — icône + libellé + valeur + tendance. Champs Ecowitt = `null` → `—` en
      Phase A.
- [ ] **Tendances généralisées** : étendre `trendLabel(data,key)` aux unités
      km/h, mm, index, W/m², hPa ; couleurs neutres pour météo ; cas spécial
      pluie ; mise en évidence pression en baisse.
- [ ] **Sélecteur de mesure du graphique** : remplacer les cases exclusives par
      des **pilules** (`Températures` = groupe air/surface/4pieds ; puis une
      pilule par mesure mono-axe : Humidité, Vent, Pluie, UV, Luminosité,
      Pression). Généraliser `humMode` → `chartMetric` (bascule axe Y + unité,
      masque l'axe °F hors températures).
- [ ] **`fetchData`** : transporter `wind/gust/rain/uv/solar/press` dans les
      3 branches (raw / bucket horaire / `/daily`), avec garde `!= null` comme
      `airv/hum`.
- [ ] **Tuile phase de lune** (SunCalc, voir section Lune).
- [ ] **Panneau solunaire** (SunCalc + calcul majeures/mineures).
- [ ] **i18n FR/EN** : nouveaux libellés (mesures, phases, majeures/mineures,
      lever/coucher).
- [ ] **Responsive** : grilles auto-fit ; mobile conserve le comportement
      actuel (vertical). Tester ≤480 px.

## Tâches — Lune + Solunaire (calcul 100 % client)

- [ ] Charger **SunCalc** depuis cdnjs (`.../suncalc/1.9.0/suncalc.min.js` —
      CDN autorisé).
- [ ] Constante `LAKE = { lat, lon }`.
- [ ] **Tuile phase** : `getMoonIllumination` → fraction + phase → icône +
      « 78 % · gibbeuse ».
- [ ] **Solunaire** :
  - [ ] Majeures = ±1 h autour du transit (altitude lune max) et de
        l'anti-transit (min) — balayage journalier via `getMoonPosition`.
  - [ ] Mineures = ±0.5 h autour de `getMoonTimes` (lever/coucher lune).
  - [ ] Cote du jour (★) selon proximité nouvelle/pleine lune.
  - [ ] Barre 24 h positionnant majeures/mineures + marqueurs soleil
        (`getTimes`) et lune.
- [ ] Vérifier les heures contre une table solunaire en ligne pour la date.

## Tâches — Firebase

- [ ] **Modèle de données** `readings/{ms}` : nouveaux champs optionnels
      `airb, humb, wind, gust, wdir, rrate, rday, uv, solar, press`
      (rétro-compat : absents gérés côté frontend).
- [ ] **`/daily/{ms}`** : ajouter les agrégats avec **règles par métrique** :
  - moyenne : temp, pression, UV, luminosité, humidité
  - **somme** : pluie cumul (`rday`)
  - **moyenne + max** : vent (`wind` moy, `gustmax`)
- [ ] Étendre `firebase_put_daily` + le calcul du script (selectattr-guarded,
      comme `airv/hum`) — dépend de la Phase B (données présentes).
- [ ] Supprimer + reconstruire `/daily` une fois l'agrégation étendue (comme
      fait pour véranda/humidité).
- [ ] Règles RTDB : inchangées (lecture publique `readings`+`daily`, écriture
      `ha-writer`) — rien à faire.

## Tâches — Home Assistant (`home_assistant.yaml`) — Phase B

- [ ] Configurer l'**intégration Ecowitt** (Settings → Devices → Ecowitt ;
      pointer WSView Plus « Customized » vers l'IP de HA). Passerelle GW3002
      dans le boathouse (WiFi + 120 V) — **même réseau que HA** requis.
- [ ] **Fournir les noms d'entités** `sensor.<ecowitt>_*` (débloque le reste).
- [ ] `manitou_firebase` payload : ajouter
      `airb/humb/wind/gust/wdir/rrate/rday/uv/solar/press`. `airb`/`humb` (WN32)
      deviennent la source primaire d'air/humidité.
- [ ] Adapter le helper `val('air')` frontend à la nouvelle priorité
      WN32 → véranda → quai.
- [ ] **NE PAS** intégrer `sensor.chalet_*` (Honeywell) pour l'instant —
      l'analyse a montré qu'à l'emplacement #1 la sonde est amortie par la masse
      du mur (biais opposé à la véranda, pas meilleure). À réévaluer après
      déplacement au #2 (nord, déportée du mur) + nouvelle comparaison.

## Tâches — Backfill des données

- [x] **Véranda/humidité** : déjà fait (`backfill_veranda.py`).
- [ ] **Ecowitt** : PAS de backfill possible (données inexistantes avant
      l'installation). L'historique météo démarre à l'installation.
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

## Tâches — Idées futures (non implémentées, à planifier)

Backlog capturé le 2026-07-07, rien de ceci n'est implémenté — à détailler et
prioriser avant de commencer.

- [ ] **Tuile Lune → icône de phase + %** : remplacer/compléter l'affichage
      actuel par une icône représentant visuellement la phase (croissant,
      gibbeuse, pleine…) à côté du pourcentage — voir photo de référence
      fournie par Ben. Trouver ou construire un set d'icônes de phase lunaire
      (SVG) cohérent avec le style Tabler du reste du site.
- [ ] **Panneau solunaire en modal** : au lieu d'une section dans le flux de la
      page, le panneau solunaire complet s'ouvre en **popup/modal** au clic sur
      la tuile Lune (dans la section Ciel & conditions). Réduit la hauteur de
      la page principale ; garder la tuile Lune (phase+%) comme point d'entrée.
- [ ] **Renommer la section graphique** : le titre actuel « Historique des
      températures » ne couvre plus toutes les mesures (météo incluse).
      Chercher un nom plus général — pistes à évaluer : « Données historiques »,
      « Tendances », « Évolution », « Historique ». Décider avec Ben.
- [ ] **Photo horaire (webcam)** : capturer une photo à chaque heure (caméra à
      définir — ESP32-CAM ? webcam IP ? téléphone dédié ?) et l'afficher sur le
      site (dernière photo, ou petite galerie/timelapse). Implique : choix du
      matériel, stockage des images (Firebase Storage plutôt que RTDB), un
      pipeline de capture + upload, gestion de la rétention (combien de photos
      garder).
- [ ] **Navigation temporelle sur le graphique** : pouvoir choisir un jour, un
      mois ou une année précis dans le passé (pas seulement des fenêtres
      glissantes 24h/7j/30j/Saison/Année) — un vrai sélecteur de date pour
      « remonter dans le temps ». Implique une UI de sélection de date +
      requêtes RTDB par plage arbitraire (déjà possible via `orderBy`+
      `startAt`/`endAt` sur la clé timestamp).
- [ ] **Lien vers une vue radar** : ajouter un lien (ou embed) vers un radar
      météo externe (ex. Environnement Canada, Windy, RainViewer) centré sur le
      lac, pour visualiser la pluie/les orages qui approchent.
- [ ] **Prévisions météo (forecast)** : afficher des prévisions à court terme.
      Implique de choisir une source (API météo tierce — Environnement Canada,
      OpenWeather, etc. — car Ecowitt ne fournit pas de prévisions) et de
      décider où/comment les afficher sur le site.

---

## Questions ouvertes / à confirmer

- Coordonnées GPS exactes du lac (solunaire).
- Noms d'entités Ecowitt (Phase B).
- Stats du graphique en mode mono-mesure : 4 cartes fixes vs mesure affichée.
- Sonde chalet : à réévaluer après déplacement au #2.
- WiFi boathouse = même sous-réseau que HA ? (requis pour le push local Ecowitt).
