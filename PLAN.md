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

- [x] Confirmer les **coordonnées GPS du lac** — ✅ fait : 46.0471, -74.3739
      (lues depuis la config HA), en dur dans la constante `LAKE`.
- [x] Valider l'ordre final des tuiles dans « Ciel & conditions » — ✅ Vent,
      Pluie, UV, Luminosité, Lune (phase).
- [ ] **Décider du comportement des stats sous le graphique** — pas encore
      tranché : `renderStats` affiche toujours codé en dur seulement
      `['air','surface','depth','humidity']`, ne couvre pas encore
      pression/vent/pluie/UV/luminosité même si ces mesures ont des données.

## Tâches — Front End (`index.html`)

- [x] **Variables CSS couleur** — ✅ `--wind --rain --uv --solar --pressure
      --moon` (+ `--radar` ajouté depuis pour la section Prévisions).
- [x] **Sections catégorisées** — ✅ Air & atmosphère / Eau du lac / Ciel &
      conditions, chacune avec en-tête de section.
- [x] **Nouvelles tuiles** — ✅ Pression, Vent, Pluie, UV, Luminosité, Lune
      toutes présentes, affichent `—` tant que Phase B n'a pas de données.
- [x] **Tendances généralisées** — ✅ `trendLabel` gère les unités par mesure,
      couleurs neutres pour la météo, mise en évidence pression en baisse.
      ⚠️ **Sauf la pluie** : pas encore le traitement spécial « sec / X mm/h »
      prévu — passe actuellement par la flèche générique ↑/↓ (peu pertinent
      pour un cumul quotidien qui ne fait que monter). À corriger.
- [x] **Sélecteur de mesure du graphique** — ✅ fait, mais avec des **cases à
      cocher exclusives** (pas des pilules comme prévu à l'origine) : logique
      généralisée `SOLO`/`seriesVisible` qui bascule axe Y + unité. Fonctionne,
      juste un choix visuel différent de l'esquisse initiale.
- [x] **`fetchData`** — ✅ **partiel** : le brut (24h) et `/daily` transportent
      tous les champs (spread `...obj[k]`). ⚠️ **Le bucket horaire (7j/30j)
      n'agrège PAS encore vent/pluie/UV/luminosité/pression** — seuls
      air/surface/depth/airv/hum sont moyennés ; ces mesures disparaîtraient
      sur les vues 7 jours/30 jours une fois les données Ecowitt branchées.
      **Vrai bloquant pour la Phase B, à corriger avant de brancher Ecowitt.**
- [x] **Tuile phase de lune** — ✅ icône SVG dynamique (voir section Lune).
- [x] **Panneau solunaire** — ✅ accordéon (voir section Lune).
- [x] **i18n FR/EN** — ✅ tous les libellés mesures/phases/majeures-mineures/
      lever-coucher présents dans les deux langues.
- [ ] **Responsive** : pas testé systématiquement ≤480px depuis les derniers
      ajouts (accordéons Lune/Radar, section Prévisions). À valider.

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
- [ ] Vérifier une fois les heures contre une table solunaire en ligne pour
      confirmer la précision (jamais fait formellement).

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
- [ ] **Aligner les séparateurs Solaire/Lune** : les lignes horizontales avant
      Sunrise (tuile Solaire) et Moonrise (tuile Lune) ne sont pas exactement à
      la même hauteur malgré la structure `.card-value-row` partagée entre les
      deux tuiles (2026-07-07 — tentative faite, pas encore résolu). À reprendre
      avec un examen plus précis en dev tools (line-height réel du texte de
      tendance vs du chiffre, padding/marge résiduelle).
- [x] **Renommer la section graphique** : ✅ fait (2026-07-07) — renommé en
      « Historique des données » / « Historical data ».
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
- [x] **Radar météo embarqué** : ✅ fait (2026-07-07) — nouvelle section
      « Prévisions » (entre Ciel & conditions et les onglets de période),
      positionnée délibérément comme catégorie « ce qui s'en vient » (externe/
      prédictif) distincte des mesures propres au site. Tuile Radar en
      accordéon (même pattern que la Lune), carte Windy centrée sur le lac,
      **iframe chargée seulement à la première ouverture** (économie de bande
      passante). `.forecast-row` (flex, pas grille) déjà dimensionné pour
      accueillir les tuiles de prévisions 7 jours à côté, sans réorganisation.
- [ ] **Prévisions météo 7 jours (forecast)** : la section « Prévisions » n'a
      pour l'instant que le radar — reste à ajouter les tuiles de prévisions
      elles-mêmes. Implique de choisir une source (API météo tierce —
      Environnement Canada, OpenWeather, etc. — Ecowitt ne fournit pas de
      prévisions) et de construire les tuiles jour (icône + min/max) dans
      `.forecast-row`, à côté de la tuile Radar existante.

---

## Questions ouvertes / à confirmer

- Coordonnées GPS exactes du lac (solunaire).
- Noms d'entités Ecowitt (Phase B).
- Stats du graphique en mode mono-mesure : 4 cartes fixes vs mesure affichée.
- Sonde chalet : à réévaluer après déplacement au #2.
- WiFi boathouse = même sous-réseau que HA ? (requis pour le push local Ecowitt).
