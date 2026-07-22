# Calendrier d'activité chasse-pêche — spec d'implémentation

> Document de handoff pour le dev. Décrit une **page dédiée cachée** (route `/cp`
> sur le site actuel) — un **Calendrier d'activité solunaire + météo** avec bascule
> **Pêcheur / Chasseur**, cote par facteurs (Lune · Pression · Vent · Direction),
> vues Jour / Semaine / Mois et navigation jour par jour. Le **panneau « Activité
> lunaire » actuel reste** sur `lmt` mais **perd sa cote ★** (redevient purement
> astronomique). Accès à la page cachée par **appui long sur la tuile Lune**.
>
> **Mockup interactif de référence** : [`mockups/calendrier-activite.html`](mockups/calendrier-activite.html)
> — ouvrir dans un navigateur, tout est cliquable (toggle, granularité, clic sur
> une journée, flèches ‹ ›). C'est la source de vérité visuelle ; ce `.md` est la
> source de vérité pour la **logique, les données et les seuils**.
>
> Statut backlog suivi dans [`PLAN.md`](PLAN.md). Contexte système :
> [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 1. Objectif

Le panneau actuel (accordéon « Activité lunaire », fonction `updateMoon()` dans
`index.html`) affiche une cote **★ purement lunaire** et les périodes majeures/
mineures d'un seul jour (aujourd'hui). Deux mouvements :

- **On garde ce panneau sur `lmt`** mais on lui **retire la cote ★** — il redevient
  purement informatif (phase, %, majeures/mineures, soleil/lune). Voir §10.B.
- **On crée une page dédiée cachée** (route `/cp`, voir §10) — le **calendrier
  d'activité** qui répond à la vraie question d'un chasseur-pêcheur : *« quels sont
  les bons jours, et pourquoi ? »*. Accès par appui long sur la tuile Lune (§10.C).

Trois changements de fond :

1. **Bascule Pêcheur / Chasseur** — la lune n'agit pas pareil sur le poisson et
   le cerf. Le toggle recalcule la cote (pas juste un changement d'icône).
2. **La météo entre dans la cote** — pression et vent comptent autant que la lune.
   Cote = moyenne pondérée de **4 facteurs** (Lune, Pression, Vent, Direction du
   vent), **poids configurables et persistés** ; c'est le scoring de chaque facteur
   qui change selon l'activité.
3. **Navigation temporelle** — vues Jour / Semaine / Mois, clic sur une journée
   pour le détail, flèches ‹ › pour avancer/reculer d'un jour.

Les **étoiles deviennent des poissons ou des cerfs** ; seul le **total** porte
l'icône animale, chaque facteur a un mini-score neutre (points ●●●○).

---

## 2. Modèle de cote (le cœur)

### 2.1 Quatre sous-scores, chacun de 1 à 4

| Facteur | Entrée | Toujours dispo ? |
|---|---|---|
| **Lune** | phase lunaire (SunCalc, calcul client) | ✅ oui, tout jour passé ou futur |
| **Pression** | pression MSL + tendance sur 24 h (hPa) | ❌ horizon ~14 j (voir §3) |
| **Vent** | vitesse moyenne du jour (km/h) | ❌ horizon ~14 j |
| **Direction** | direction dominante du vent (`wdir`, 8 secteurs) | ❌ horizon ~14 j (+ voir §3.2 pour le passé) |

### 2.2 Score de la Lune (diffère selon le mode)

`phase` ∈ [0,1) : 0 = nouvelle lune, 0.5 = pleine lune (`SunCalc.getMoonIllumination().phase`).

```
// Pêche : pic à la nouvelle ET à la pleine lune (syzygie)
fishMoon(phase):
  d = min(phase, 1-phase, |phase-0.5|)
  d < 0.035 → 4 ;  d < 0.10 → 3 ;  d < 0.17 → 2 ;  sinon 1

// Chasse : pic à la NOUVELLE lune (nuits sombres → mouvement diurne),
//          creux à la pleine lune (nuits claires → activité nocturne)
deerMoon(phase):
  dn = min(phase, 1-phase)          // 0 = nouvelle, 0.5 = pleine
  dn < 0.06 → 4 ;  dn < 0.16 → 3 ;  dn < 0.32 → 2 ;  sinon 1
```

C'est la différence la plus importante entre les deux modes : **une pleine lune
donne 4 poissons mais ~1 cerf**.

### 2.3 Score de la Pression (identique aux deux modes)

`delta` = pression moyenne du jour − pression moyenne de la veille (hPa/24 h).
La **chute** avant un front est le signal prédictif pour les deux activités.

```
pressScore(delta):
  delta ≤ -3 → 4   (chute marquée, front qui arrive)
  delta ≤ -1 → 3   (en baisse)
  delta <  2 → 2   (stable)
  sinon      → 1   (en hausse / haute pression « bluebird »)
```

### 2.4 Score du Vent (diffère selon le mode)

`spd` = vitesse moyenne du jour en km/h.

```
// Pêche : une légère « ride » (walleye chop) est idéale ; calme plat et tempête nuisent
fishWind(spd):
  8 ≤ spd ≤ 15 → 4   (ride idéale)
  5 ≤ spd < 20 → 3   (clapot léger)
  spd < 28     → 2   (calme plat <5, ou clapot fort 20-28)
  sinon        → 1   (trop fort)

// Chasse : un vent modéré porte l'odeur et masque le bruit ; trop de vent cloue le gibier
deerWind(spd):
  8 ≤ spd ≤ 18 → 4   (porte l'odeur, masque le bruit)
  5 ≤ spd < 24 → 3
  spd < 30     → 2   (trop calme <5 = bruit ; ou soutenu 24-30)
  sinon        → 1   (gibier au sol)
```

### 2.4b Score de la Direction du vent (diffère selon le mode)

`dir` = secteur dominant sur 8 points (N, NE, E, SE, S, SO, O, NO).

```
// Pêche : dicton du vent d'ouest
//   « wind from the west, fish bite the best ; from the east, bite the least »
fishDir(dir):
  O, SO → 4
  S, SE → 3
  N, NO → 2
  E, NE → 1

// Chasse : heuristique front froid (FAIBLE CONFIANCE — voir note)
deerDir(dir):
  N, NO → 4   (souvent post-front froid → pic de mouvement)
  O, NE → 3
  E, SO → 2
  S, SE → 1   (air chaud, haute pression → plus lent)
```

> ⚠️ **La direction à la chasse est très dépendante du site et du mirador** (on
> chasse le vent de face selon l'emplacement), pas une qualité « bonne/mauvaise »
> universelle. Ces valeurs sont une heuristique de départ à valider ; le poids
> configurable permet de la réduire à 0 si elle ne colle pas. Piste future :
> scorer plutôt la **stabilité** du vent, ou la direction **relative aux miradors**
> de Ben.

### 2.5 Poids et total

**Quatre facteurs. Poids configurables et persistés** (mêmes valeurs pour les
deux modes ; c'est le *scoring* de chaque facteur qui diffère selon le mode, pas
les poids). Valeurs de départ :

```
Facteur      Poids défaut
Lune          .35
Pression      .35
Vent          .10
Direction     .20
              ────
              1.00

total = moon·wMoon + press·wPress + wind·wWind + dir·wDir   // continu, 1.0–4.0
coteAffichée = clamp(round(total), 1, 4)                    // 1–4 icônes animales
```

- **Persistance** : sauvegarder l'objet poids et les seuils modifiés côté client.
  Ben a demandé un **cookie**. ⚠️ *Recommandation* : utiliser plutôt
  **`localStorage`** (clé `lm_activity_weights`, JSON) pour rester cohérent avec
  les autres préférences du site (`lm_lang`, `lm_unit_*`) — c'est fonctionnellement
  équivalent et c'est le mécanisme fiable sur le domaine Firebase (le passage à
  localStorage était la raison de quitter GAS, ARCHITECTURE §1). Si un vrai cookie
  est requis, l'indiquer.
- **UI de réglage** : un petit panneau « Réglages » (4 sliders de poids +
  éventuellement les seuils) — peut être livré en v1.1 ; le **strict minimum v1**
  est l'objet de config lu depuis le stockage avec les défauts ci-dessus, plus la
  possibilité de l'éditer.
- **Centraliser** tous les seuils ET les poids dans un objet de config en tête de
  fichier, ex. `const SCORING = { weights:{moon:.35,press:.35,wind:.10,dir:.20},
  wind:{...}, press:{...}, dir:{...} }`, hydraté depuis le stockage au chargement.

**Hors horizon météo** (jour > ~14 j) : Pression, Vent **et Direction** = `null`,
`total = moonScore`, badge « Lune seule ». Ne jamais inventer de score météo.
(Les 3 facteurs météo arrivent ou manquent ensemble — même source.)

> ⚠️ **Tous les seuils et poids sont des valeurs de départ à valider** avec Ben
> (connaissance du lac).

---

## 3. Couche de données (source météo hybride)

La lune se calcule toujours localement (SunCalc). La météo vient de **3 sources
selon la position temporelle du jour**, choisies pour maximiser la fiabilité :

| Jour | Source | Détail |
|---|---|---|
| **Aujourd'hui** | Capteur Ecowitt (RTDB) + Environnement Canada | Pression + vent live du capteur ; tendance pression = `press` actuel − `press` d'il y a ~6 h (lu dans `/readings`). EC en secours pour la tendance. Badge « Capteur + EC ». |
| **Passé** | `/daily` (déjà agrégé) | `press` (moyenne), `wind` (moyenne), `gustmax`. Tendance = moyenne du jour − moyenne de la veille. Badge « Mesuré ». |
| **Futur ≤ 14 j** | **Open-Meteo** | Nouvelle dépendance externe. Badge « Open-Meteo ». |
| **Futur > 14 j** | — | Lune seule. Badge « Lune seule ». |

### 3.1 Open-Meteo — endpoint

Gratuit, sans clé, CORS OK. Récupérer les données **horaires** et agréger par
jour local côté client (cohérent avec l'archi « option A, agrégation client, pas
de Cloud Functions ») :

```
https://api.open-meteo.com/v1/forecast
  ?latitude=46.0471&longitude=-74.3739
  &hourly=pressure_msl,wind_speed_10m,wind_gusts_10m,wind_direction_10m
  &timezone=America%2FToronto
  &forecast_days=16
```

- Unité de vent Open-Meteo par défaut = **km/h** (déjà cohérent avec le capteur,
  ne pas passer `wind_speed_unit`).
- `pressure_msl` = pression au niveau de la mer en hPa → comparable au `press`
  du capteur (qui est aussi relatif/MSL, voir ARCHITECTURE §11).
- **Agrégation client par jour local** : moyenne de `pressure_msl` → valeur du
  jour ; delta = moyenne(jour) − moyenne(jour−1) ; `wind_speed_10m` moyen →
  score vent ; direction dominante = mode de `wind_direction_10m`.
- **Cache** : réponse en `localStorage`, TTL 1 h (même cadence que la carte
  prévisions EC déjà en place). Recalcul des scores des jours futurs à partir du
  cache, pas de refetch par jour.
- **Échec réseau** : les jours futurs retombent sur « Lune seule » + badge, jamais
  d'écran vide (mêmes règles que la carte prévisions EC qui se masque en silence).

### 3.2 Réutilisation de l'existant — et le trou « direction passée »

- `/readings` porte déjà `press`, `wind`, `gust`, `wdir` → **aujourd'hui** (lecture
  live) a tout, y compris la direction, sans changement.
- ✅ **RÉSOLU (2026-07-17)** — `wdirdom` a été **ajouté à l'agrégation HA**
  (`home_assistant.yaml` : payload `firebase_put_daily` + calcul dans
  `script.manitou_aggregate_daily`). `/daily` porte désormais la **direction
  dominante du jour en degrés**, calculée en **moyenne vectorielle** (sin/cos puis
  `atan2` — jamais une moyenne arithmétique, qui donnerait 180° pour 350°+10°).
  Écrit `null` si la résultante est trop faible (vent variable) plutôt qu'un
  0°=Nord trompeur. Le front mappe les degrés vers les 8 secteurs (§2.4b).
- ⚠️ **Le changement du 2026-07-17 n'avait jamais atteint la production.** Il avait
  été appliqué à la copie de documentation `home_assistant.yaml` (hors dépôt depuis
  `3431fdb`) mais pas au HA vivant : ni le `data:` du script, ni le `payload` du
  `rest_command`. Résultat, `wdirdom` était **absent de 100 % des buckets** jusqu'au
  2026-07-22, sans la moindre erreur — un champ manquant dans le payload ne casse
  rien. Déployé pour de bon le 2026-07-22.
- ⚠️ **L'historique n'est pas rétro-rempli automatiquement** : le script saute les
  jours déjà présents dans `/daily`. **Reconstruit à la main du 12 au 21 juillet 2026**
  (suppression des 10 buckets puis relance du script). Le **11 juillet et avant reste
  sans `wdirdom`** — hors de la fenêtre `range(1, 11)` — donc le fallback ci-dessous
  reste nécessaire en permanence.
- **Fallback quand `wdirdom` est absent** (jours pré-migration, ou `null` = vent
  variable) : direction = `—`, facteur exclu, **poids renormalisés** sur les 3
  autres pour ce jour.
- **Renormalisation** : si un seul facteur manque (direction passée en fallback),
  renormaliser les poids restants pour qu'ils somment à 1 sur ce jour. Si les
  **quatre facteurs météo** manquent (hors horizon), on retombe sur Lune seule.
- **Aujourd'hui et futur** portent la direction (`wdir` capteur / Open-Meteo
  `wind_direction_10m` dominante) → pas de trou, seul le passé est concerné.
- **SunCalc déjà chargé** (CDN, `index.html`) + constante `LAKE = {lat:46.0471,
  lon:-74.3739}` déjà définie → réutiliser pour phase, `getMoonPosition`
  (transit → majeures), `getMoonTimes` (lever/coucher → mineures), `getTimes`
  (soleil).
- **Champs météo épars dans l'historique** : `press`/`wind` n'existent que depuis
  ~7 juillet 2026. Pour un jour passé sans ces champs → facteurs Pression/Vent à
  `—` (comme hors horizon), cote sur la lune seule.

---

## 4. Modèle d'interaction

| Décision | Contrôle |
|---|---|
| **Activité** | Toggle segmenté **Pêcheur / Chasseur** (haut à droite) |
| **Granularité** | Segmenté **Jour · Semaine · Mois** |
| **Position** | Clic sur une journée (grille/liste) → détail ; flèches **‹ ›** = ±1 jour ; **Aujourd'hui** = retour au présent |

- Basculer le mode recalcule **toute** la grille + le détail (scores, poids,
  couleur d'accent, icône).
- Changer de granularité **conserve la journée sélectionnée** (Mois → Jour ouvre
  le détail du jour sélectionné, pas d'aujourd'hui par défaut).
- Clavier `←` / `→` : jour précédent/suivant en vue Jour.

---

## 5. Mise en page (Proposition A retenue)

### 5.1 En-tête du panneau
```
[🐟 icône]  Activité solunaire            [ 🐟 Pêcheur | 🦌 Chasseur ]
            MODE PÊCHE                          toggle segmenté
```

### 5.2 Sélecteur de granularité (centré)
```
              [ Jour | Semaine | Mois ]
```

### 5.3 Vue Mois (défaut)
Grille calendrier 7 colonnes. Chaque cellule :
```
┌─────────┐
│ 14    🌒 │   ← n° du jour (haut-g) + glyphe de phase (haut-d)
│         │
│ 🐟🐟🐟🐟 │   ← cote du jour (icônes sm), lueur de fond ∝ score
└─────────┘
```
- Fond : lueur d'accent d'intensité `score/4`.
- Aujourd'hui : bordure accent. Sélectionné : fond accent.
- Jour **hors horizon météo** : petit point gris en bas-droite.
- Clic → passe en vue Jour sur cette date.
- Légende : `🐟🐟🐟🐟 excellente · 🐟 faible · • hors horizon météo`.

### 5.4 Vue Semaine
7 rangées, une par jour :
```
[ jeu        ]  🐟🐟🐟🐟   [▓▓░░░▓▓▓░░ barre 24h mini]
  9 juil
```

### 5.5 Vue Jour = le détail (aussi affiché en aperçu sous Mois/Semaine)

```
┌──────────────────────────────────────────────────────────────┐
│ mardi 14 juillet 2026                    [🕐 Aujd] [ ‹ ] [ › ] │  ← stepper
│ 🌒 Gibbeuse croissante · 68% éclairée                          │
│                                                                │
│ ┌─ FACTEURS DE LA COTE · PÊCHE ───────────  Capteur + EC ─┐    │
│ │ 🌙 Lune       ●●●○  moyen · gibbeuse croissante     35% │    │
│ │ 🎚 Pression   ●●●●  ▼ chute · front qui arrive·1006hPa35%│   │
│ │ 💨 Vent       ●●○○  ride idéale · 12 km/h           10% │    │
│ │ 🧭 Direction  ●●●●  vent d'ouest favorable · O      20% │    │
│ │ ────────────────────────────────────────────────────── │    │
│ │ TOTAL         🐟🐟🐟🐟          Journée exceptionnelle  │    │
│ └──────────────────────────────────────────────────────── ┘   │
│                                                                │
│ [▓▓░░░░▓▓▓▓░░░░░░▓▓░░░░  barre 24h : majeures/mineures/nuit/●] │
│ 0h        6h        12h        18h        24h                  │
│                                                                │
│ ┌ MAJEURE 1 ─┐ ┌ MAJEURE 2 ─┐ ┌ MINEURE 1 ┐ ┌ MINEURE 2 ┐    │
│ │ 6:12–8:12  │ │ 18:24–20:24│ │ 0:47–1:47 │ │ 12:35–13:35│    │
│ └────────────┘ └────────────┘ └───────────┘ └───────────┘    │
│                                                                │
│ ☀ Lever 5:18   ☀ Coucher 20:42   🌙 Lune 1:12 / 15:40         │
│ ▏ Conseil pêche : cale tes sorties sur les majeures + …        │
└──────────────────────────────────────────────────────────────┘
```

**Bloc facteurs** :
- 3 rangées : icône + nom, **points ●●●○** (score 1–4, neutres accent), lecture
  contextuelle, poids %.
- Badge source en haut-droite (« Capteur + EC » / « Mesuré » / « Open-Meteo » /
  « Lune seule »).
- Ligne **Total** avec les icônes animales (seul endroit où elles apparaissent
  dans le bloc) + verdict.
- Hors horizon : rangées Pression/Vent grisées à `—` + note explicative.

**Stepper** (`.day-step`) :
- `‹` / `›` = ±1 jour, recalcul complet. La sélection suit dans la grille si on
  revient en vue Mois/Semaine.
- « Aujourd'hui » (icône horloge) visible seulement si la date ≠ aujourd'hui.

---

## 6. Mobile (≤ 480 px)

- En-tête empile ; toggle mode pleine largeur.
- Granularité : rangée scrollable horizontale (ou reste 3 boutons, tient à 320 px).
- **Cases du calendrier (vue Mois) — point serré validé** : à 7 colonnes sur
  téléphone une case fait ~35-42 px ; **4 icônes poisson/cerf n'y tiennent pas**
  (elles débordent/se coupent, vérifié). Adaptation retenue : **sur ≤ 480 px, les
  cases affichent le score numérique (1-4)** en couleur d'accent au lieu des 4
  icônes ; l'intensité du fond (glow ∝ score) reste. Les icônes animales restent
  sur desktop et dans le **détail** (au tap). Alternative possible : une seule
  icône animale + le chiffre. À confirmer sur appareil réel.
- Bloc facteurs : la lecture contextuelle passe sous les points/poids (`flex-wrap`,
  `.fx-read{flex-basis:100%}`).
- Stepper `‹ ›` : cibles ≥ 44 px.
- Cibles tactiles ≥ 44 px partout.
- **Note de validation** : l'aperçu intégré n'a pas pu descendre sous ~980 px de
  viewport réel (limite outillage) ; validé par simulation en conteneur contraint
  + géométrie. À re-vérifier à l'œil sur mobile réel (dans les critères §13).

---

## 7. Composants visuels

- **Icône poisson / cerf** : SVG inline (voir `ICON.fish` / `ICON.deer` dans le
  mockup). Total uniquement.
- **Points de facteur** : 4 `<i>` ronds, `n` remplis en couleur d'accent.
- **Glyphe de phase lunaire** : SVG à arcs elliptiques généré depuis
  `illumination.phase` (réutiliser `moonPhaseSVG()` déjà dans `index.html`).
- **Accent CSS** : variable `--accent` basculée entre `--fish #2dd4bf` (teal) et
  `--deer #e0913f` (ambre) via `body[data-mode]`. Réutilise les tokens existants
  (`--pressure`, `--wind`, `--moon` déjà définis).
- **Barre 24 h** : bandes absolues — majeures (±1 h, forte), mineures (±0.5 h,
  faible), nuit (avant lever / après coucher soleil), marqueur « maintenant »
  (seulement le jour courant).

---

## 8. i18n (FR / EN — table existante)

| Clé | FR | EN |
|---|---|---|
| activité | Activité solunaire | Solunar activity |
| mode pêche / chasse | Pêcheur / Chasseur | Angler / Hunter |
| granularité | Jour / Semaine / Mois | Day / Week / Month |
| facteurs | Facteurs de la cote | Rating factors |
| lune/pression/vent | Lune / Pression / Vent | Moon / Pressure / Wind |
| total | Total | Total |
| verdicts pêche | Journée creuse / Activité modérée / Bonne journée / Journée exceptionnelle | Slow day / Moderate / Good day / Exceptional |
| verdicts chasse | Peu favorable / Passable / Favorable / Très favorable | Poor / Fair / Good / Excellent |
| lecture pression | chute · front qui arrive / en baisse / stable / en hausse | sharp drop · front / falling / steady / rising |
| lecture vent (pêche) | calme plat / ride idéale / clapot / trop fort | dead calm / ideal chop / choppy / too rough |
| lecture vent (chasse) | trop calme / porte l'odeur / soutenu / gibier au sol | too still / carries scent / gusty / deer bedded |
| direction | Direction | Direction |
| lecture direction (pêche) | vent d'ouest favorable / défavorable | west wind favours / against |
| lecture direction (chasse) | quadrant froid favorable / air chaud | cool quadrant / warm air |
| majeure/mineure | Majeure / Mineure | Major / Minor |
| sources | Capteur + EC / Mesuré / Open-Meteo / Lune seule | Sensor + EC / Measured / Open-Meteo / Moon only |
| hors horizon | hors horizon (météo non prévisible au-delà de ~14 j) | beyond horizon (no forecast past ~14 days) |
| aujourd'hui | Aujourd'hui | Today |
| aria ‹ › | Jour précédent / Jour suivant | Previous day / Next day |

---

## 9. Fuseau & bornes temporelles

- Toutes les bornes de jour en **America/Toronto** (comme la nav temporelle du
  graphique, voir TIME_TRAVEL_SPEC §7), pas UTC ni le fuseau du visiteur.
- ⚠️ **Attention au décalage `/daily`** : les buckets `/daily` sont agrégés à
  **minuit UTC** (ARCHITECTURE §4.2), ~4-5 h avant le jour civil québécois. Pour
  une **moyenne journalière**, l'écart est invisible → acceptable en v1 (même
  arbitrage que TIME_TRAVEL_SPEC §8.4). Documenter le choix.
- Précision lune : le transit SunCalc a ~12-17 min d'écart vs USNO (plafond du
  modèle, déjà validé dans PLAN.md) — sans impact sur des fenêtres ±1 h.

---

## 10. Architecture à deux pages + entrée cachée

Décidé : le calendrier n'est **pas** un panneau dans `index.html`, mais une **page
séparée cachée** sur le même site. Le panneau lunaire de `index.html` reste, sans ★.

### 10.A — Nouvelle page `cp.html` (le calendrier)

- **Fichier autonome** `cp.html` à la racine, déployé sur le **même site Firebase**
  que `index.html` (pas de sous-domaine — décision produit). Aucun changement RTDB :
  lecture publique de `/readings` et `/daily`, comme `index.html`.
- **URL propre via rewrite Firebase** — ajouter dans `firebase.json` :
  ```json
  "hosting": { ... , "rewrites": [ { "source": "/cp", "destination": "/cp.html" } ] }
  ```
  → accessible à `lmt.bcourchesne.com/cp`. (Ce n'est pas un secret cryptographique —
  RTDB est public en lecture de toute façon ; c'est une page « pour initiés », pas
  une zone sécurisée.)
- **Réutilise** : SunCalc (CDN), la constante `LAKE`, les tokens CSS (`--moon`,
  `--pressure`, `--wind`, `--fish`, `--deer`…), le helper `moonPhaseSVG()`, la
  logique de lecture RTDB (`fetch` REST) et l'i18n FR/EN de `index.html`. Extraire
  le commun dans un petit `shared.js` est un plus, mais **dupliquer est acceptable**
  en v1 (cohérent avec le « pas de build » du projet). JS vanilla.
- **Couche météo** : module `weatherForecast` (fetch Open-Meteo + cache localStorage
  1 h + agrégation jour), helper `dayWeather(date)` routant capteur / `/daily` /
  Open-Meteo / null selon la position (§3).
- **Mémoïsation** : `breakdown(date)` mémoïsé par `mode|dateKey` (jours passés + lune
  immuables ; invalider seulement aujourd'hui au refresh et le cache Open-Meteo au TTL).
- **Auto-refresh** : ne recalcule qu'aujourd'hui ; ne re-ancre jamais la journée
  sélectionnée (même règle que la nav du graphique).

### 10.B — Modification de `index.html` (panneau lunaire conservé, sans ★)

- Dans `updateMoon()` : **retirer uniquement la ligne de cote ★** (`starStr` et son
  rendu). Garder nom de phase, % éclairé, majeures/mineures, lever/coucher soleil
  et lune, l'accordéon et la tuile Lune. Le panneau redevient purement astronomique.

### 10.C — Entrée cachée : appui long sur la tuile Lune

- **Geste** : `pointerdown` sur la tuile Lune → démarrer un timer de **1200 ms** ;
  si `pointerup` / `pointerleave` / `pointercancel` avant la fin → annuler (c'est un
  clic simple normal → l'accordéon s'ouvre comme d'habitude). Si le timer arrive au
  bout → **naviguer vers `/cp`**. Aucun conflit avec l'accordéon (clic court = accordéon,
  appui long = porte cachée).
- **Souris ET tactile** : les Pointer Events couvrent les deux — à la souris,
  **maintenir le bouton gauche enfoncé ~1,2 s** déclenche le geste. **Ne démarrer le
  timer que sur le bouton principal** (`e.button === 0`, ou `e.isPrimary`) pour qu'un
  clic droit (menu contextuel) ne l'arme pas. `user-select: none` sur la tuile pendant
  l'appui évite qu'un maintien souris démarre une sélection de texte. (L'appui long est
  instinctif au doigt, moins à la souris — acceptable pour un accès volontairement caché.)
- **Anti-parasites** : `touch-action: none` / `user-select: none` sur la tuile pendant
  l'appui, `preventDefault` sur le `contextmenu` mobile (empêche le menu « copier »
  au long-press), respecter `prefers-reduced-motion` pour l'animation de feedback.
- **Feedback discret** : à ~1000 ms, la tuile/lune **pulse** (glow accent ~400 ms) +
  mini-toast « 🎣 Chasse-pêche », puis navigation. L'utilisateur comprend qu'il a
  déclenché quelque chose d'intentionnel.
- **Mémoire de déverrouillage** : au 1er succès, poser `localStorage.lm_cp_unlocked=1`
  et afficher dès lors un **petit lien discret dans le footer** (« 🎣 Chasse-pêche »)
  pour ne plus refaire le geste. Réversible (le retrait du flag re-cache le lien).
- **Retour** : `cp.html` a un lien/*chevron* « ‹ Retour » vers `lmt` (`/` ou
  `index.html`).

---

## 11. Cas limites

- **Open-Meteo indisponible** → jours futurs = Lune seule + badge, pas d'erreur.
- **Capteur/EC muets aujourd'hui** → aujourd'hui aussi en Lune seule.
- **Jour passé sans `press`/`wind`** (avant ~7 juil 2026) → Pression/Vent à `—`.
- **DST** : jours de 23 h / 25 h — calculer les bornes avec `Intl`, ne pas
  supposer 1440 min (la barre 24 h peut simplifier, mais les bornes de fetch non).
- **Avance vers le futur : LIBRE** (décidé) — le stepper avance sans limite ;
  au-delà de 14 j la cote passe en Lune seule (informatif, pas d'écran vide).
- **Grille Mois SUIT le stepper** (décidé) — reculer/avancer hors du mois affiché
  change le mois de la grille : `STATE` doit porter le mois affiché de la vue Mois
  et le recaler sur `sel` quand on y revient (ou en continu). Passer d'un 31 à un 1er
  traverse bien le mois.

---

## 12. Ordre de construction suggéré

1. **Squelette `cp.html`** + rewrite `/cp` (§10.A) : page vide qui lit le RTDB,
   réutilise SunCalc/LAKE/tokens. Déployable tout de suite.
2. **Modèle de cote** (§2) isolé + config des seuils/poids. Testable sans UI.
3. **Couche données** (§3) : `dayWeather(date)` avec les 4 sources + cache
   Open-Meteo + fallback Lune seule.
4. **Vue Jour / détail** (§5.5) : bloc facteurs + barre 24 h + fenêtres + stepper.
   Livrable seul = déjà utile.
5. **Vue Mois** (§5.3) : grille + clic → détail.
6. **Vue Semaine** (§5.4) + toggle granularité.
7. **Toggle Pêcheur/Chasseur** : bascule le scoring par mode (Lune, Vent,
   Direction) — les poids restent partagés et configurables (§2.5).
8. **`index.html`** : retirer la cote ★ (§10.B) + entrée cachée appui long (§10.C)
   + lien footer après déverrouillage.
9. **Mobile** (§6) + i18n (§8) + **validation responsive réelle** (§13).

---

## 13. Critères d'acceptation (v1)

- [ ] Toggle Pêcheur/Chasseur : recalcule Lune + Vent + Direction + accent + icône (poisson↔cerf).
- [ ] Cote = moyenne pondérée de **4 facteurs** (Lune, Pression, Vent, Direction) ;
      total en icônes animales, facteurs en points.
- [ ] Les facteurs météo alimentent la cote depuis la bonne source selon le jour
      (capteur+EC / `/daily` / Open-Meteo), badge affiché.
- [ ] Au-delà de ~14 j (ou données manquantes) : facteurs météo = `—`, cote Lune
      seule, badge, jamais d'écran vide. Poids **renormalisés** si un seul facteur manque.
- [ ] **Poids configurables et persistés** (défauts .35/.35/.10/.20) ; rechargement
      conserve les réglages.
- [ ] Vues Jour / Semaine / Mois ; changer de granularité conserve la position.
- [ ] Clic sur une journée ouvre le détail ; flèches ‹ › = ±1 jour (**avance libre**) ;
      ←/→ clavier ; « Aujourd'hui » revient au présent ; **la grille Mois suit** le
      stepper à travers les mois.
- [ ] Bornes de jour en America/Toronto ; DST correct.
- [ ] **Page séparée `cp.html`** servie à `/cp` (rewrite Firebase), lit le RTDB public.
- [ ] **Panneau lunaire de `index.html` conservé, cote ★ retirée** (reste phase, %,
      majeures/mineures, soleil/lune, accordéon).
- [ ] **Appui long (1,2 s) sur la tuile Lune → `/cp`**, sans casser l'accordéon (clic
      court l'ouvre toujours) ; feedback discret ; lien footer après `lm_cp_unlocked`.
- [ ] **Responsive validé sur mobile réel** (320 / 360 / 375 / 414 / 480 px) : bloc
      facteurs, calendrier et stepper sans débordement ; cibles ≥ 44 px ;
      granularité scrollable.
- [ ] Toutes les nouvelles chaînes en FR **et** EN.
- [ ] Seuils/poids centralisés dans une config modifiable (objet `SCORING`).

## 14. Décisions produit

Tranché avec Ben (2026-07-14) :

1. ✅ **Poids configurables + persistés**, défauts **Lune .35 · Pression .35 ·
   Vent .10 · Direction .20** (§2.5). Persistance stockage client (cookie demandé ;
   `localStorage` recommandé — voir §2.5).
2. ✅ **Avance vers le futur : libre** (pas de borne). Lune seule au-delà de 14 j.
3. ✅ **Grille Mois : suit le stepper** à travers les mois.
4. ✅ **Emplacement : page dédiée cachée** (§10) — le calendrier vit dans un fichier
   séparé `cp.html`, route `/cp` (rewrite Firebase), **pas de sous-domaine**. Le
   panneau lunaire de `index.html` **reste mais perd sa cote ★**. Accès par **appui
   long (1,2 s) sur la tuile Lune** + lien discret au footer après déverrouillage.
5. ✅ **Direction du vent scorée**, poids **.20**, 4ᵉ facteur (§2.4b). Scoring par
   mode ; heuristique chasse à valider.

Reste à valider (pas bloquant, ajustable via la config) : les **seuils** de chaque
facteur (plages de vent, seuil de chute de pression, table de direction chasse).
