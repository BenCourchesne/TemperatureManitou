# Calendrier d'activité chasse-pêche — spec d'implémentation

> **v1 EN PRODUCTION depuis le 2026-07-22** à [`lmt.bcourchesne.com/cp`](https://lmt.bcourchesne.com/cp).
> Une **v2** est spécifiée aux §15 à §20 : elle remplace le modèle de cote par un
> **indice horaire fondé sur le régime météorologique**, ajoute un **sélecteur de
> lac** et un **journal de sorties** pour la calibration. Le §2 décrit le modèle v1,
> conservé pour mémoire mais **remplacé** par le §15.
>
> Page dédiée cachée (route `/cp`), vues Jour / Semaine / Mois, navigation jour par
> jour. Le panneau « Activité lunaire » de `lmt` reste mais **a perdu sa cote ★**
> (redevenu purement astronomique). Accès par **appui long sur la tuile Lune**.
>
> **Mockup de référence** : [`mockups/calendrier-activite.html`](mockups/calendrier-activite.html)
> — source de vérité visuelle. Ce `.md` est la source de vérité pour la **logique,
> les données et les seuils**.
>
> Statut backlog dans [`PLAN.md`](PLAN.md). Contexte système :
> [`ARCHITECTURE.md`](ARCHITECTURE.md). Modèle de référence v2 :
> `Modèle d'évaluation des conditions de pêche` v1.1 (PDF hors dépôt).

---

## 0. État d'avancement

### Livré en production (2026-07-22)

| Élément | Commit | Note |
|---|---|---|
| `cp.html` — calendrier complet, vues Jour/Semaine/Mois | `14ea1dc` | JS vanilla, sans build |
| Rewrite Firebase `/cp` | `14ea1dc` | `firebase.json` |
| Cote ★ retirée de `index.html`, entrée par appui long | `ac67fe2` | §10.B et §10.C respectés |
| `wdirdom` déployé en production + historique reconstruit | `6f753ac` | 12 au 21 juillet 2026 |
| Tendance de pression 24 h, refresh incrémental | `1cb3b6c` | remplace les 6 h du §3 |
| `.git` exclu du déploiement Hosting | `8ff5921` | le dépôt entier était servi publiquement |
| Cache HTML ramené de 1 h à 60 s | `86ad541` | les déploiements mettaient 1 h à se propager |
| Spec v2 complète (§15 à §20) | `f80e570` | modèle, multi-lacs, journal, mesures |
| Sonde de vent : diagnostic et protocole | [`PLAN.md`](PLAN.md) | `1d3f0d4`, `6d2bb42`, `4f1c8cd` |
| Journal — 1ʳᵉ entrée + correctif classificateur | `2423fed`, `dd82420` | Phase 0 close, voir §17.5 |
| **Carte Vent fusionnée** dans `index.html` | `a832b4d` | vent au large + sonde locale |
| `journal/` exclu du déploiement | `6a39f6f` | les entrées portent le secteur de pêche |
| Handoff Phase 1 + §20 documentées | `f86c7a8` | les questions ouvertes portent désormais leurs preuves |
| Horizon de prévision corrigé, §15.9b | `24cd66f` | `gem_seamless` va à 10 j, pas 16 |
| **Fondation du moteur v2** | `23f89ac` | `LAKES`, `MODEL`, `V2` — bloc `10b` de `cp.html`, additif |

### Carte Vent de `index.html` (2026-07-22)

Valeur principale = **vent au large** (modèle GEM d'Environnement Canada,
`gem_seamless` via Open-Meteo, cache 10 min) ; pied de carte = **sonde locale**,
libellée « île McCall ». La direction de la sonde n'est **pas** affichée : elle
est canalisée et prêterait à confusion (§18.5).

Motif : le 2026-07-22 à 14 h, la page annonçait **1 km/h** pendant que 22 stations
METAR mesuraient **20 km/h avec des rafales à 41** et des averses — information
dangereusement rassurante pour qui décide de sortir en chaloupe.

Repli à trois niveaux, testé : modèle injoignable → la sonde reprend la vedette
sous le libellé « Vent (île McCall) » ; ni modèle ni sonde → carte vide proprement.
Le vent au large ne venant pas du RTDB, la carte reste alimentée si la sonde se tait.

Critères d'acceptation du §13 : **tous satisfaits**, sauf la validation responsive
sur appareil réel (vérifiée par simulation à 320 / 360 / 480 px, sans débordement).

### Écarts assumés par rapport au spec d'origine

- **Badge « Capteur » et non « Capteur + EC »** — Environnement Canada n'est pas
  branché en secours. Si le capteur est muet, la journée retombe sur Open-Meteo.
- **Tendance de pression du jour sur 24 h et non 6 h** (§3) — justification et
  mesures au §18.2.
- **Cases du calendrier à 39 × 45 px** sur 360 px, sous les 44 px du §13. C'est la
  géométrie inhérente de 7 colonnes, déjà anticipée au §6. Tous les *contrôles*
  sont à ≥ 44 px.

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

## 2. Modèle de cote v1 — ⚠️ REMPLACÉ PAR LE §15

> Ce modèle est **en production** mais **remplacé** par l'indice horaire du §15.
> Conservé pour mémoire et parce que la couche de données (§3), l'interaction (§4),
> la mise en page (§5) et l'i18n (§8) restent valides en v2.
>
> Ses trois défauts, établis au §18 : il compte plusieurs fois le même front,
> il donne 35 % à la lune, et son seuil « chute marquée ≤ −3 hPa/24 h » se
> déclenche environ **un jour sur trois** — un score maximal aussi fréquent ne
> discrimine rien.

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

### 14.1 Décisions v2 (2026-07-22)

6. ✅ **Pêche uniquement.** Le toggle Pêcheur/Chasseur est retiré. La chasse
   reviendra avec son propre modèle et son propre journal — le journal de pêche ne
   pourrait de toute façon pas calibrer des scores de chasse.
7. ✅ **Indice horaire, pas journalier.** Décidé parce que le journal permet de
   juger « le modèle avait raison ou tort **à telle heure** », ce qu'une note
   journalière ne permet pas.
8. ✅ **Open-Meteo comme base uniforme** des deux lacs pour le régime, la pression
   et la direction. Le capteur Manitou devient une couche *locale* (§16.3).
9. ✅ **Journal authentifié** par un compte Firebase dédié, session persistante.
10. ✅ **Sélecteur de lac** : Manitou et Devenyns (§16).

---

# PARTIE II — v2 : indice horaire par régime

---

## 15. Modèle v2 (le nouveau cœur)

Fondé sur `Modèle d'évaluation des conditions de pêche` v1.1. Le principe directeur
est de **distinguer le régime météorologique de ses manifestations**, pour ne pas
pénaliser trois fois le même front froid.

### 15.1 Forme générale

```
indice(t) = 50
          + score_régime
          + score_pression   × réduction
          + score_direction  × réduction
          + score_vitesse_vent
          + score_lune       (plafonné à +10)
          + score_heure

indice affiché = clamp(round(indice), 0, 100)
```

`t` est une **heure locale** (America/Toronto). L'indice est recalculé pour chaque
heure de la journée ; la grille mensuelle en dérive une valeur par jour (§15.8).

**Pondérations cibles** — le PDF annonce Régime 30 % · Pression 25 % · Vent 25 % ·
Lune 10 % · Heure 10 %, mais ses plages de points ne les respectent pas (amplitudes
réelles : Régime 60, Vent 60, Pression 45, Heure 15, Lune 12). Les valeurs ci-dessous
sont **réétalonnées** pour que l'amplitude de chaque facteur corresponde à sa
pondération annoncée, et pour que l'échelle ne sature plus (§18.4).

### 15.2 Entrées horaires

Toutes issues d'Open-Meteo (`hourly`), pour les deux lacs, passé comme futur :

| Symbole | Variable Open-Meteo | Usage |
|---|---|---|
| `P` | `pressure_msl` | `dP3`, `dP6`, `dP12`, `dP24` = `P(t) − P(t−n h)` |
| `W` | `wind_speed_10m` | vitesse ; `dW6` = tendance |
| `G` | `wind_gusts_10m` | détection du passage de front |
| `D` | `wind_direction_10m` | direction ; `ΔD3` = écart angulaire sur 3 h |
| `T` | `temperature_2m` | `dT6` = refroidissement postfrontal |
| `N` | `cloud_cover` (%) | dégagement postfrontal, `dN6` = tendance |
| `R` | `precipitation` (mm) | `R3` = cumul sur 3 h |

`relative_humidity_2m` est disponible mais non utilisée en v2 — la couverture
nuageuse capte le même signal préfrontal plus directement.

### 15.3 Classificateur de régime — 30 %

Cascade à priorité décroissante ; **la première règle vraie l'emporte**.

| # | Régime | Condition | Score |
|---|---|---|---|
| 1 | **Passage du front** | `ΔD3 ≥ 60°` ET (`R3 > 0,5 mm` OU `G ≥ 25 km/h`) ET `dP3 > −0,5` ET `dP6 < −1` | `+2` |
| 2 | **Postfrontal froid** | `P − min(P sur les 18 h précédentes) ≥ 2,0` ET `dP3 ≥ +0,3` ET direction ∈ [292,5°, 67,5°] (NO/N/NE) | `−25` |
| 3 | **Front en approche** | `dP3 ≤ −1,5` ET `dW6 > 0` ET (`N ≥ 70` OU `R3 > 0`) | `+25` |
| 4 | **Préfrontal** | `−3,5 ≤ dP6 ≤ −0,8` ET `dN6 ≥ +10` | `+22` |
| 5 | **Retour à la stabilité** | `|dP3| < 1` ET postfrontal dans les 12 h précédentes ET `dW6 < 0` | `+5` |
| 6 | **Stable** | `|dP3| < 1` ET `|dP12| < 2` | `+8` |
| 7 | *Indéterminé* | (défaut) | `0` |

Le PDF donne des scores identiques (+20 à +30) aux régimes 3 et 4 ; ils sont
néanmoins distingués ici parce que la **règle anti-double-comptage** (§15.7) et
l'affichage en dépendent.

> ⚠️ **Ne pas utiliser la température pour détecter le postfrontal.** Première
> version de la règle rejetée le 2026-07-22 après confrontation à la sortie du
> 19 juillet (§17.5) : elle exigeait `dT6 ≤ −1,0`, or le **réchauffement diurne
> masque le refroidissement postfrontal** — à 10 h ce jour-là, `dT6` valait
> **+3,1 °C** alors que la masse d'air était nettement froide. Passer à `dT24`
> ne règle rien : le 19 était dégagé et le 18 couvert, donc l'ensoleillement a
> rendu l'après-midi plus chaud que la veille à la même heure.
>
> La règle retenue est **structurelle** : un régime postfrontal, c'est être sur
> la **branche montante après un creux de pression**. Aucun thermomètre requis.
> Résultat sur le 19 juillet à Devenyns : **16 h sur 17** correctement classées
> contre 4 sur 19 avec l'ancienne règle, et **24 %** du temps seulement sur les
> 14 jours de Manitou — pas de surdéclenchement.

### 15.3b Persistance des régimes (hystérésis)

Un régime météorologique est un **état physique persistant**, pas une étiquette
recalculée indépendamment à chaque heure. Sans précaution, une valeur qui frôle
un seuil fait clignoter la classification : le 19 juillet, l'heure de 13 h
sortait du régime pour un `dP3` de **+0,2 au lieu de +0,3**, au milieu de dix-sept
heures postfrontales ininterrompues.

Deux garde-fous, à appliquer après la cascade :

1. **Seuil de sortie plus exigeant que le seuil d'entrée** — une fois dans un
   régime, y rester tant que les conditions ne s'en écartent pas d'une marge
   franche (environ la moitié du seuil d'entrée).
2. **Comblement des trous d'une heure** — si `t−1` et `t+1` portent le même
   régime et que `t` en diffère, aligner `t` sur ses voisins.

Durée minimale d'un régime : **3 heures**. En deçà, fusionner avec le voisin
dominant.

### 15.4 Pression — 25 %

Le PDF utilise plusieurs fenêtres au lieu d'en élire une : la courte détecte les
extrêmes et le calme, les longues portent les tendances graduelles. Validé sur les
données réelles au §18.3.

| État | Condition | Score |
|---|---|---|
| Chute rapide | `dP3 ≤ −3` OU `dP6 ≤ −5` | `+15` |
| Baisse lente | `−3 ≤ dP6 ≤ −1` OU `−5 ≤ dP12 ≤ −2` | `+20` |
| Stable | `|dP3| < 1` ET `|dP12| < 2` | `+7` |
| Hausse lente | `+1 ≤ dP6 ≤ +3` OU `+2 ≤ dP12 ≤ +5` | `−3` |
| Hausse rapide | `dP3 ≥ +3` OU `dP6 ≥ +5` | `−15` |

**Interpolation** : plutôt que des paliers, interpoler linéairement entre les
bornes de chaque état — une chute de 3,8 hPa/6 h ne doit pas valoir exactement le
même score qu'une chute de 5,2.

**Pression absolue** (§2.6 du PDF) : facteur secondaire, `−3` au-dessus de
1025 hPa, `0` ailleurs. Volontairement faible — une haute pression stable depuis
plusieurs jours vaut mieux qu'une pression moyenne qui vient de bondir.

### 15.5 Vent — 25 %

**Vitesse** (voir question ouverte §20.1 sur l'échelle de référence) :

| Plage | Score |
|---|---|
| 0-4 km/h — presque calme | `−3` |
| 5-9 km/h — léger | `+5` |
| 10-18 km/h — modéré | `+13` |
| 19-28 km/h — soutenu | `+8` |
| 29-39 km/h — fort | `0` |
| ≥ 40 km/h — très fort | `−15` |

**Direction** — table **propre à chaque lac** (§16.4), valeurs de départ Manitou :

| N | NE | E | SE | S | SO | O | NO |
|---|---|---|---|---|---|---|---|
| −15 | −10 | 0 | +3 | +5 | +10 | +5 | −10 |

⚠️ Ces valeurs sont à réexaminer : voir §18.5 et la question §20.2.

**Vent du nord** (§3.3 du PDF) — le §3.3 **remplace** la ligne « N » du tableau, il
ne s'y ajoute pas, sous peine de cumuler jusqu'à −40 :

- nord *isolé* (pression stable, pas de refroidissement, direction constante
  depuis plusieurs jours) → `−7`
- nord *postfrontal* (régime 2 actif) → `−20`

### 15.6 Lune — 10 %, plafonné à +10

| Événement | Score |
|---|---|
| Nouvelle lune (±1,5 j) | `+4` |
| Pleine lune, pêche de nuit ou aube | `+4` |
| Pleine lune, milieu de journée | `0` |
| Premier / dernier quartier | `+1` |
| Lever ou coucher de lune ±90 min | `+4` |
| Transit supérieur ou inférieur ±90 min | `+2` |

Le total lunaire est **plafonné à +10** : une bonne période lunaire ne doit jamais
transformer une journée postfrontale en excellente journée.

### 15.7 Heure de la journée — 10 %

| Fenêtre | Score |
|---|---|
| Aube — de −60 min à +90 min du lever du soleil | `+9` |
| Matin — de +90 min après le lever jusqu'à 10 h 30 | `+5` |
| Milieu de journée | `−3` |
| Fin de journée — 2 h avant le coucher | `+6` |
| Crépuscule — ±45 min du coucher | `+9` |
| Nuit | `0` |

La pénalité de milieu de journée est **annulée** si `N ≥ 70 %` et `W ≥ 10 km/h`
(ciel couvert et vent modéré). La nuit reste à 0 : son effet dépend trop de
l'espèce recherchée pour un score générique.

### 15.8 Règle anti-double-comptage

C'est l'apport principal du modèle. Lorsque plusieurs facteurs découlent du même
front, on garde l'intégralité du score de régime et on **réduit de moitié** ceux
qui ne font que le refléter.

```
réduction = 0,5  si régime ∈ {passage, postfrontal, approche, préfrontal}
            1,0  si régime ∈ {stable, retour, indéterminé}
```

Elle s'applique à **la pression et à la direction du vent**. La **vitesse** du vent
conserve son plein effet : elle agit sur la pêchabilité concrète, pas sur le régime.

### 15.9 Agrégation journalière

L'indice est horaire, la grille mensuelle est journalière. La cellule d'un jour
porte **la meilleure fenêtre de 2 h de la journée**, pas la moyenne :

```
indice_jour   = max sur t de moyenne(indice, [t, t+2h])
fenêtre_jour  = l'intervalle qui atteint ce maximum
```

Affichage : « Jeudi · 78 · meilleure fenêtre 19 h 30 – 21 h 00 ». C'est ce qui
répond à la vraie question — *quand* y aller, pas seulement *quel jour*.

### 15.9b Meilleures fenêtres à venir — le classement transversal

Le §15.9 donne la meilleure fenêtre **de chaque journée**. Il en faut un second
niveau : **classer les fenêtres entre elles** sur tout l'horizon, pour répondre à
la question qui décide vraiment d'une sortie — *quand y aller dans les dix
prochains jours*.

```
1. calculer l'indice horaire sur tout l'horizon
2. lisser par moyenne glissante de 2 h
3. retenir les maxima locaux dont l'indice dépasse le seuil (défaut 60)
4. plafonner à 2 fenêtres par jour, pour que la liste couvre l'horizon
   au lieu de s'agglutiner sur la meilleure journée
5. trier par indice décroissant, garder les 6 premières
```

Affichage proposé, en tête de la vue Mois :

```
PROCHAINES FENÊTRES
  jeu 24 juil.  19 h 30 – 21 h 00   84   préfrontal · SO 14 km/h
  sam 26 juil.  05 h 15 – 07 h 00   79   stable · aube
  jeu 24 juil.  05 h 00 – 06 h 30   76   préfrontal · aube
```

Chaque ligne porte le **régime** et le facteur dominant : savoir *pourquoi* une
fenêtre est bonne vaut autant que le score, et c'est ce qui permet de juger le
modèle plutôt que de le suivre aveuglément.

**Fiabilité selon l'échéance** — à indiquer visuellement, sans quoi une fenêtre à
9 jours paraît aussi sûre qu'une à demain :

| Échéance | Fiabilité |
|---|---|
| 0-2 j | bonne — HRDPS puis RDPS |
| 3-5 j | correcte — le régime est fiable, l'heure exacte moins |
| 6-10 j | indicative — tendance seulement |
| > 10 j | hors modèle → lune seule |

### 15.10 Configuration

Tous les seuils, scores et tables dans un objet `MODEL` unique en tête de fichier,
remplaçant `SCORING`, hydraté depuis `localStorage` (clé `lm_cp_model`) et
éditable. Structure : `{ regimes, press, wind, dir, moon, hour, correlation, lakes }`.

---

## 16. Multi-lacs

### 16.1 Registre

`const LAKE` devient un registre. La sélection est persistée (`lm_cp_lake`).

| Clé | Nom | Latitude | Longitude | Altitude | Capteur |
|---|---|---|---|---|---|
| `manitou` | Lac Manitou | 46,0471 | −74,3739 | 431 m | oui (Ecowitt) |
| `devenyns` | Lac Devenyns | 47,0496 | −73,8241 | 402 m | non |

Distance : ~119 km nord-nord-est. **Même fuseau** (America/Toronto), aucun
traitement particulier. Mais un front traversant à 40 km/h met ~3 h à passer de
l'un à l'autre : les indices ne seront pas identiques le même jour, et c'est
correct — chaque lac interroge Open-Meteo à ses propres coordonnées.

SunCalc doit prendre les coordonnées **du lac sélectionné** : 1° de latitude
décale le lever du soleil de plusieurs minutes.

### 16.2 Source de données

Open-Meteo pour les deux lacs, **`models=gem_seamless`** (GEM d'Environnement
Canada — HRDPS 2,5 km aux échéances courtes, puis RDPS, puis GDPS), avec
`past_days=92&forecast_days=11`. Cache `localStorage` par lac, TTL 1 h.

⚠️ **Horizon réel de `gem_seamless` : 10,4 jours**, mesuré le 2026-07-22 — et non
16. Demander davantage renvoie des `null` sur les derniers jours. Horizons des
autres modèles, pour mémoire : `gem_hrdps_continental` 2,4 j, `gem_regional`
3,9 j, `gem_global` 10,4 j, `best_match` 16 j.

Le choix de 10 jours plutôt que les 16 de `best_match` est assumé : au-delà d'une
semaine la classification de régime n'a plus de valeur prédictive réelle, et
mieux vaut afficher « lune seule » qu'un régime inventé. `gem_seamless` a en
outre le mérite d'être le **même modèle que la carte Vent** de `index.html`, donc
cohérent d'une page à l'autre.

`SCORING.horizonDays` de la v1 (15) doit passer à **10**.

Au-delà de 92 jours : `archive-api.open-meteo.com` (réanalyse ERA5, ~5 jours de
latence), même format de réponse.

**Écartés** : *Windy* revend surtout ECMWF et GFS — déjà servis par Open-Meteo —
mais exige une clé et impose des quotas. *Environnement Canada* a des stations trop
clairsemées près de Devenyns pour alimenter l'indice ; éventuellement utile pour le
radar ou les avertissements.

### 16.3 Rôle du capteur Manitou

Le capteur **ne sert plus au régime ni au score**. Il alimente une couche *locale*,
distincte :

| Usage | Source | Pourquoi |
|---|---|---|
| Régime, pression, direction du vent | **Open-Meteo** | c'est le flux **régional** qui définit un front ; identique aux deux lacs et comparable dans le temps |
| Clapot, contrôle du bateau, rive exposée (§3.4 du PDF) | **capteur** | c'est le vent **local au quai** qui compte pour pêcher, abri compris |

Cette séparation est ce qui rend Manitou et Devenyns notés sur la même échelle.
Sans elle, la calibration croisée serait faussée dès le départ. Elle donne aussi
un rôle au `wdirdom` reconstruit : le vent local est exactement l'entrée du
facteur « rive exposée ».

### 16.4 Table de direction par lac

La table du §15.5 est calibrée sur Manitou. La géométrie des rives de Devenyns
étant différente, elle ne se transpose pas. Devenyns démarre donc avec une
**table neutre (tout à 0)**, que son propre journal calibrera.

---

## 17. Journal de sorties et calibration

Le §11 du PDF est la partie la plus précieuse du modèle : sans données de captures,
tous les poids sont des hypothèses. **Sa valeur croît avec le temps écoulé** — d'où
son inclusion dès la v2 plutôt qu'après.

### 17.1 Principe fondamental

**Le journal stocke les *entrées* météo, jamais le score.** Sinon, chaque ajustement
de seuil rendrait tout l'historique de calibration inexploitable. En conservant les
conditions, n'importe quelle version future du modèle peut être **rejouée sur toutes
les sorties passées**. C'est ce qui rend la calibration cumulative.

### 17.2 Schéma `/journal/{pushId}`

```json
{
  "lac": "manitou",
  "debut": 1784592000000,
  "fin": 1784606400000,
  "espece": "doré",
  "captures": 3,
  "touches": 7,
  "secteur": "baie nord",
  "technique": "traîne",
  "note": 4,
  "commentaire": "…",
  "conditions": [ { "t": …, "P": …, "W": …, "D": …, "T": …, "N": …, "R": … } ],
  "cree": 1784606500000
}
```

`conditions` = instantané horaire Open-Meteo couvrant `[debut − 24 h, fin]`, pour que
les fenêtres de tendance 3/6/12/24 h soient reconstituables sans dépendre de la
disponibilité future de l'API.

### 17.2b Champs de confiance — obligatoires

Toute donnée rapportée porte un **niveau de confiance**. Sans lui, un souvenir
vague finit pondéré comme une mesure, et la calibration se corrompt d'autant plus
sournoisement qu'on n'en garde aucune trace.

- `resultat_confiance` — `compte` (captures dénombrées à la sortie) ·
  `estime` (ordre de grandeur) · `memoire` (rapporté après coup, sans comptage)
- `observations_terrain[].confiance` — `mesure` (instrument) · `bonne`
  (référence visuelle fiable : vagues franches, drapeau, ruban) · `faible`
  (estimation à l'œil, ressenti)

Repère pour juger une direction estimée à l'œil : l'erreur courante est de
**±30 à 45°**. Un écart de cet ordre entre observation et modèle ne constitue
donc **ni une confirmation ni une contradiction** — il faut le consigner comme
tel plutôt que de l'interpréter.

### 17.3 Authentification

Compte Firebase dédié (email/mot de passe), créé dans la console par Ben,
connexion une fois sur `/cp`, session persistante. Règles :

```json
"journal": {
  ".read": true,
  "$id": { ".write": "auth.uid === '<UID_BEN>' " }
}
```

Le mot de passe n'est saisi que par Ben dans le formulaire de connexion Firebase.

### 17.4 Vue calibration

Pour chaque sortie : indice prédit sur la fenêtre (rejoué avec le modèle courant)
en regard de **captures/heure** ou **touches/heure**. Plus un nuage de points
indice/succès, et le même découpage par régime — c'est lui qui tranchera le §12.

**Attente réaliste** : premières tendances vers 30-50 sorties, ajustement sérieux
au-delà de 100.

### 17.5 Sortie n° 1 — Lac Devenyns, dimanche 2026-07-19

Première entrée du journal, saisie rétroactivement le 2026-07-22. Conditions
horaires figées dans [`journal/2026-07-19-devenyns.json`](journal/2026-07-19-devenyns.json)
avant expiration de la fenêtre de 92 jours d'Open-Meteo.

**Résultat rapporté : pêche médiocre** — confiance `memoire`, sans comptage.
*(Heures de sortie, espèce ciblée, captures et secteur restent à compléter.)*

**Observation terrain** — Ben était présent sur place. Vent perçu « du nord »,
confiance `faible` (estimation à l'œil depuis le lac, sans instrument). Le modèle
donne **313° (NO)**, moyenne vectorielle avec R = 0,994. L'écart de ~47° tombe
dans la marge normale d'une estimation visuelle : l'observation est **cohérente
avec le modèle sans le confirmer** — quadrant nord dans les deux cas, précision
insuffisante pour trancher davantage.

Conditions (Open-Meteo `gem_seamless`, coordonnées de Devenyns) :

| | |
|---|---|
| Pression | **hausse continue** 1003,6 → 1011,1 hPa (+7,5 sur la journée) |
| Vent | **NO toute la journée**, 17-24 km/h, rafales **37 à 55** |
| Température | 12,5 à 17,3 °C — air frais |
| Ciel | 100 % couvert à l'aube, **0 % de 7 h à 12 h** — dégagement franc |
| Pluie | négligeable |

**Régime : postfrontal froid**, cas d'école. Hausse de pression, vent de
nord-ouest, air frais, ciel qui se dégage, fortes rafales — les cinq
caractéristiques du §1.5 du modèle de référence, qui le note **−20 à −30** et le
donne « fortement associé à une diminution de la qualité de pêche ».

**Le modèle prédit correctement ce résultat.** C'est sa première confrontation à
une observation réelle, et elle est concluante.

> ⚠️ **Ce que cette sortie ne démontre pas.** Un seul point ne valide pas un
> modèle : il est cohérent avec lui, sans plus. Le régime postfrontal était ici
> tellement marqué que presque n'importe quelle formulation l'aurait attrapé.
> Sa vraie valeur a été de **révéler un défaut du classificateur** (voir §15.3),
> pas de confirmer les pondérations.

---

## 18. Mesures et constats sur les données

Tout ce qui suit a été mesuré le 2026-07-22 sur les données réelles, pas estimé.

### 18.1 Marée atmosphérique — négligeable ici

Amplitude semi-diurne mesurée sur 350 h : **0,13 hPa**. Contribution maximale à un
écart de 3 h : 0,19 hPa ; sur 6 h : 0,27 hPa.

Le « ±1-1,5 hPa » du commit `5768c18` est un ordre de grandeur trop élevé — c'est
une valeur tropicale, pas de 46°N. **La marée n'est donc pas un facteur** dans le
choix des fenêtres. Ce qui faisait basculer l'ancien indicateur de tuile était bien
le **bruit d'arrondi** (pression en entiers avant le 2026-07-22 : ±0,5 hPa par point,
±1 hPa sur l'écart, contre un seuil à 0,3).

### 18.2 Pourquoi 24 h et non 6 h pour la cote v1

Motif retenu : **comparabilité**. Les jours passés se calculent en moyenne du jour
moins moyenne de la veille ; le jour courant devait partager cette base. Chaque
extrémité est moyennée sur 3 h pour neutraliser la quantification entière de
l'historique. *(Le motif « marée » invoqué initialement était erroné — voir §18.1.)*

### 18.3 Distribution des écarts de pression — 350 h

| Fenêtre | médiane \|Δ\| | p90 | min | max |
|---|---|---|---|---|
| 3 h | 0,85 | 2,00 | −4,58 | +3,00 |
| 6 h | 1,50 | 3,33 | −8,58 | +5,17 |
| 12 h | 2,75 | 5,92 | −13,25 | +10,00 |
| 24 h | 5,00 | 10,33 | −17,25 | +12,00 |

Les seuils du PDF tiennent : « stable < 1 hPa/3 h » couvre **56 %** du temps,
« rapide ≥ 3 hPa/3 h » reste un événement rare à **2,4 %**. Bien calibré.

En revanche le seuil v1 « chute marquée ≤ −3 hPa/24 h » se déclenche environ **un
jour sur trois** — un score maximal aussi fréquent ne discrimine rien.

> ⚠️ **Réserve** : 15 jours d'été seulement, régime convectif. L'hiver synoptique
> donnera des amplitudes plus grandes. À revalider après une saison complète.

### 18.4 Saturation de l'échelle du PDF

L'exemple 2 du PDF (préfrontal, SO 14 km/h, fin de journée) atteint **107, écrêté à
100**. Maximum théorique 150, minimum −42 : environ un tiers de l'amplitude est
perdu à chaque bout, et la discrimination disparaît précisément dans la zone 65-90.
Les scores du §15 sont réétalonnés en conséquence.

### 18.5 ⚠️ L'anémomètre de Manitou est mal exposé

Comparaison capteur / Open-Meteo sur 14 jours (337 heures appariées) :

| Grandeur | Écart médian capteur − Open-Meteo |
|---|---|
| Pression | **−1,22 hPa** (p10 −1,94 / p90 −0,30) |
| Vitesse du vent | **−7,26 km/h** (p10 −11,75 / p90 −2,59) |
| Température | **+2,08 °C** (p10 +0,45 / p90 +4,32) |
| Direction | **76° d'écart absolu médian** (p90 139°) |

L'écart de direction **n'est pas un décalage de montage**. Ventilé par direction
réelle (Open-Meteo, vent > 5 km/h) :

| Direction réelle | n | Écart du capteur |
|---|---|---|
| SE | 10 | −5° |
| S | 3 | −37° |
| **SO** | 34 | **+119°** |
| **O** | 58 | **+51°** |
| **NO** | 26 | **+34°** |

Lorsque le vent vient réellement du **SO, de l'O ou du NO**, le capteur affiche
systématiquement **N à NNO** (320-350°). Seuls les vents de sud-est sont lus
correctement. Un obstacle — relief, ligne d'arbres, bâtiment — canalise tout le
quadrant ouest vers un axe nord-nord-ouest. Le biais de vitesse de −7,3 km/h
confirme un capteur abrité.

**Conséquences :**

1. Le **§12 du PDF n'est pas testable** avec la direction du capteur : « nord »
   y regroupe le vrai nord, le nord-ouest postfrontal (mauvais) *et* le sud-ouest
   préfrontal (bon).
2. La table de direction du §15.5, calibrée sur des observations Manitou, encode
   peut-être cette distorsion — d'où la question §20.2.
3. C'est la justification première du choix d'Open-Meteo comme base uniforme (§16.3).

> Une vérification physique reste souhaitable : par vent établi, comparer la
> direction affichée à celle des vagues ou d'un drapeau. Open-Meteo est un modèle,
> pas une vérité terrain.

### 18.6 Couverture de `/daily`

24 seaux, du 28 juin au 21 juillet 2026. `press` et `wind` seulement depuis le
8 juillet ; `wdirdom` du 12 au 21 juillet. Les jours antérieurs n'ont pas de météo
exploitable — d'où les cases « sans données météo » de la grille.

---

## 19. Plan d'implémentation v2

### Phase 0 — ✅ FAITE (2026-07-22)

Le classificateur a été écrit, passé sur l'historique Open-Meteo heure par heure,
puis **corrigé deux fois** par confrontation aux données réelles :

1. **Détection du postfrontal par la température : abandonnée.** Le réchauffement
   diurne masque le refroidissement postfrontal (§15.3). Remplacée par une règle
   structurelle fondée sur la remontée depuis un creux de pression. Passage de
   4/19 à **16/17 heures** correctement classées sur le 19 juillet, sans
   surdéclenchement (24 % du temps sur 14 jours).
2. **Persistance des régimes ajoutée** (§15.3b) — une heure sortait du régime pour
   0,1 hPa d'écart au milieu de 17 heures continues.

Validé contre la première sortie du journal (§17.5, Devenyns 19 juillet, pêche
médiocre → postfrontal froid correctement identifié).

### Phase 1 — Moteur horaire ⬅️ **EN COURS**

**Point de départ.** Tout se passe dans [`cp.html`](cp.html) (~1 300 lignes,
vanilla JS, sans build). Les règles à implémenter sont aux §15.1 à §15.9, la
config au §15.10, les décisions produit au §14.1.

#### ✅ Fondation déjà en place — bloc `10b` de `cp.html` (commit `23f89ac`)

Ajout **purement additif** : le modèle v1 n'a pas été touché, la page se comporte
comme avant. Ne pas réimplémenter, mais compléter.

| Livré | Contenu |
|---|---|
| `LAKES` | Registre Manitou/Devenyns, coordonnées, table de direction par lac (§16.1, §16.4) |
| `MODEL` | Config complète du §15.10 — régimes, pression, vent, lune, heure, corrélation, hystérésis. Horizon à 10 j. |
| `V2.load(lac)` | Série horaire Open-Meteo `gem_seamless` par lac, cache 1 h, variables du §15.2 |
| `V2.regimeAt(h,i)` | Cascade du §15.3, règle postfrontal structurelle |
| `V2.classify(lac)` | Régimes de toute la série + persistance du §15.3b |
| `V2.strip(lac,date)` | Bande de 24 caractères — outil de relecture humaine |
| `secteurDe(deg)` | Degrés → 8 secteurs |

Testable en console, sans interface :

```js
await V2.load('devenyns');
V2.strip('devenyns', '2026-07-19');   // → FFFFFFFFFFFFFFFFFFFFFFFF
```

Validé le 2026-07-22 : le 19 juillet à Devenyns ressort **24 h sur 24 en
postfrontal froid**, cohérent avec la pêche médiocre du §17.5 ; et **17 %** de
postfrontal sur 600 h pour chacun des deux lacs, donc pas de surdéclenchement.

#### ⬜ Reste à faire

1. **Les cinq facteurs de score** — §15.4 pression, §15.5 vent (vitesse et
   direction), §15.6 lune plafonnée, §15.7 heure du jour. Les barèmes sont dans
   `MODEL`, il manque les fonctions qui les appliquent.
2. **Règle anti-double-comptage** (§15.8) — `MODEL.correlation` est prêt.
3. **`indexAt(lac, i)`** — assemblage du §15.1, indice 0-100 pour une heure.
4. **`dayIndex(lac, jour)`** — meilleure fenêtre de 2 h (§15.9).
5. **`meilleuresFenetres(lac)`** — classement transversal (§15.9b).
6. **Réétalonnage** — ajuster l'échelle pour que le 99ᵉ centile tombe vers 92 (§20.3).
7. **Basculer les vues** de `breakdown()`/`scoreOf()` vers les nouvelles fonctions,
   puis retirer `SCORING` et le mode Chasseur (§14.1 décision 6).

Les points 1 à 5 sont testables en console avant de toucher à l'interface.

**À conserver tel quel** — cette couche est éprouvée et indépendante du modèle :

| Bloc | Rôle |
|---|---|
| §2 « Dates civiles en America/Toronto » | `civOf`, `zonedMidnight`, `civSpan`, `civAdd`… — arithmétique DST-safe |
| §5 Astronomie | `solunar()`, `moonPhaseSVG()`, `phaseIndex()` |
| §6 `fetchForecast` / cache localStorage | à étendre, pas à réécrire |
| §8 Formatage, §9 Rendu, §10 Interactions | vues Jour/Semaine/Mois, stepper, clavier |
| i18n FR/EN | table `I18N`, ajouter les clés v2 |
| Panneau de réglages | remplacer les 4 sliders de poids par l'édition de `MODEL` |

**À remplacer** :

| Existant v1 | Devient |
|---|---|
| `const SCORING` | `const MODEL` (§15.10), clé `lm_cp_model` |
| `breakdown(c)` — un score 1-4 par jour | `indexAt(lake, t)` — un indice 0-100 par **heure** |
| `moonScore` / `pressScore` / `windScore` / `dirScore` | les cinq facteurs du §15.4 à §15.7 |
| `dayWeather(c)` — capteur/`/daily`/Open-Meteo | Open-Meteo seul pour le régime (§16.3) |
| `scoreOf(c)` | `dayIndex(lake, c)` = meilleure fenêtre de 2 h (§15.9) |
| Toggle Pêcheur/Chasseur | **retiré** (§14.1 décision 6) |

**Changements de la couche données** :

- `past_days=92`, `models=gem_seamless`, variables du §15.2 (ajouter
  `temperature_2m`, `cloud_cover`, `precipitation`).
- Cache `localStorage` **par lac** (`lm_cp_forecast_<lac>`), TTL 1 h.
- Registre `LAKES` remplaçant `const LAKE` (§16.1), sélection dans `lm_cp_lake`.

**Ordre suggéré** : `MODEL` et le classificateur d'abord, testables en console
sans toucher à l'interface ; puis `indexAt()` ; puis `dayIndex()` ; puis brancher
les vues existantes dessus. L'interface (Phase 2) ne bouge qu'ensuite.

**Réétalonnage** : après le premier calcul complet, vérifier que le 99ᵉ centile de
l'indice historique tombe vers 92 (§20.3) et ajuster l'échelle globale en
conséquence. Les scores du §15 sont des valeurs de départ, pas un étalonnage.

**Deux questions ouvertes bloquent partiellement** : §20.1 (échelle des vitesses de
vent) et §20.2 (table de direction). Les recommandations y sont documentées avec
les preuves ; il manque la confirmation de Ben. En attendant, implémenter avec les
recommandations et garder les valeurs dans `MODEL` pour les changer d'une ligne.

### Phase 2 — Interface

- Barre 24 h existante : courbe de l'indice au lieu des seules fenêtres solunaires.
- Cellule du mois : indice + heure de la meilleure fenêtre.
- **Bandeau « Prochaines fenêtres »** (§15.9b) en tête de la vue Mois — le
  classement transversal des meilleures fenêtres de l'horizon, avec régime,
  facteur dominant et indication de fiabilité selon l'échéance. C'est ce qui
  répond directement à « quand sortir ».
- Vue jour : décomposition par facteur, **régime en tête**, avec mention explicite
  de la réduction anti-double-comptage quand elle s'applique.
- Sélecteur de lac en haut de page.
- i18n FR/EN de toutes les nouvelles chaînes.

### Phase 3 — Journal

- Connexion Firebase (§17.3) et règles de sécurité.
- Formulaire de saisie, écriture dans `/journal` avec instantané des conditions.
- Vue calibration : indice prédit contre captures/heure, découpage par régime.

### Phase 4 — Calibration continue

Non planifiable : dépend de l'accumulation des sorties. Premiers ajustements
attendus vers 30-50 sorties.

---

## 20. Questions en suspens

### 20.1 ⏳ Échelle de référence des vitesses de vent — OUVERTE

Les plages du §15.5 (0-4 calme, 5-9 léger, 10-18 modéré…) proviennent du PDF.
La v2 note sur Open-Meteo, or le capteur lit **7,3 km/h de moins** (§18.5).

**Réponse de Ben (2026-07-22)** : « de ce qu'affichait ma station ».

**⚠️ Contredit par les données.** Si les plages étaient à l'échelle du capteur :

| Plage du modèle | % des lectures capteur sur 14 j |
|---|---|
| 0-4 « presque calme » | **75,6 %** |
| 5-9 « léger » | 13,7 % |
| 10-18 « modéré, meilleures conditions » | **4,8 %** |
| 19-28 « soutenu » | 0,2 % |
| 29-39 « fort » | **0 %** |
| 40+ « très fort » | **0 %** |

Le capteur n'a jamais dépassé **29,5 km/h** en vent moyen : les deux dernières
plages sont physiquement inatteignables et trois quarts du temps tomberait dans
« presque calme ». Un découpage dont la meilleure plage ne survient que 4,8 % du
temps et dont deux catégories n'existent pas ne peut pas être celui qui a été
conçu.

**Recommandation** : garder les plages telles quelles et les appliquer à
Open-Meteo, à l'échelle « terrain dégagé » à laquelle elles correspondent
manifestement. **En attente de confirmation de Ben.**

### 20.2 ⏳ Origine de la table de direction — OUVERTE

**Réponse de Ben (2026-07-22)** : « sur ce qu'affichait la station ».

**⚠️ La table devient alors auto-contradictoire.** Correspondance mesurée entre
affichage et réalité (§18.5) :

| Station affiche | n | Vent réel |
|---|---|---|
| **N** | 81 | **SO 48 · O 24** · NO 7 (moyenne 245° = SO) |
| **NO** | 124 | **O 57 · SO 44** · NO 23 (moyenne 265° = O) |
| SE | 17 | SE 10 · S 4 |
| SO | **1** | O 1 |

La table donne **N = −15** (le pire) et **SO = +10** (le meilleur) — or c'est
physiquement le même vent. Et la station n'a affiché « SO » qu'**une seule fois**
en 14 jours : le +10 pour le sud-ouest ne peut pas en venir, il vient du dicton
*« wind from the west, fish bite the best »*.

La table est donc **d'origine mixte** — le dicton pour le quadrant ouest,
l'expérience réelle pour le nord — et n'est pas inversible proprement.

**Recommandation** : repartir d'une **table neutre pour Manitou aussi**, et
laisser le journal la reconstruire. **En attente de confirmation de Ben.**

> 💡 **L'hypothèse la plus intéressante en sort.** Si l'observation « vent du nord
> = mauvaise pêche » est réelle et vient de l'expérience, alors au Lac Manitou
> **c'est le vent de sud-ouest à ouest qui déçoit** — l'inverse du dicton. Le §12
> se reformule : non plus « le nord est-il cause ou indicateur », mais « pourquoi
> l'ouest déçoit-il ici alors qu'il devrait être favorable ». Piste probable : le
> quai est **abrité du vent d'ouest** par la crête (§18.5), donc l'eau accessible
> reste calme quand souffle le vent dominant — la bonne rive serait à l'est du
> lac. Testable dès la prochaine sortie par vent d'ouest établi.

### 20.3 ✅ Ce que doit signifier 100 — RÉSOLUE

**Réponse de Ben (2026-07-22)** : une **journée exceptionnelle, quelques-unes par
saison**.

**Méthode retenue** : réétalonner empiriquement pour que le **99ᵉ centile de
l'indice sur l'historique tombe vers 92**, ce qui laisse le 100 aux journées
vraiment rares et préserve la discrimination entre 65 et 90 — la zone où se
décident les sorties.
