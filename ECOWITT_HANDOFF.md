# Handoff — Intégration station Ecowitt (GW3002 + WS69 + WN32) → Phase B

> **But de ce document** : brief autonome pour une **nouvelle session Claude Code**.
> Tout le contexte nécessaire est ici — pas besoin de relire l'historique.
> Projet : site météo Lac Manitou (Firebase Hosting + Realtime Database).
> Répertoire : `D:\Claude desktop\ESPHome\manitou`. Branche git : `weather-station`.

---

## 0. Ce qui est DÉJÀ fait (ne PAS refaire)

Le **frontend (`index.html`) est prêt** à recevoir les données Ecowitt — Phase A
est complète et déployée sur le canal de test. Concrètement, ces éléments
existent déjà et fonctionnent avec `—` en attendant les données :

- Tuiles Pression, Vent, Pluie, UV, Luminosité (section « Ciel & conditions »).
- Helper `val(d, key)` (index.html ~ligne 881) qui lit déjà les champs :
  - `air` → `airb` ?? `airv` ?? `air`  (priorité **boathouse WN32 → véranda → quai**)
  - `humidity` → `humb` ?? `hum`
  - `pressure` → `press`, `wind` → `wind`, `rain` → `rday`, `uv` → `uv`, `solar` → `solar`
- `fetchData` transporte tous les champs sur **24h / 7j / 30j / saison / année**
  (bucket horaire généralisé via `RAW_PROP`, moyenne par mesure).
- i18n FR/EN des libellés météo, couleurs CSS (`--wind --rain --uv --solar
  --pressure`), tendances généralisées (`trendLabel`).

**Conséquence** : dès que les champs `airb/humb/wind/gust/rday/rrate/uv/solar/press`
apparaissent dans `/readings/{ms}` sur Firebase, **les tuiles s'allument toutes
seules**. Le gros du travail Phase B est donc **côté Home Assistant**, pas côté
frontend.

**Il reste toutefois 2 petits ajustements frontend** (voir §5).

---

## 1. Matériel (rappel)

- **GW3002** : passerelle/console, possède le **baromètre** (→ pression) et
  reçoit les capteurs sans fil. Installée dans le **boathouse** (WiFi + 120 V).
  ⚠️ Doit être sur le **même sous-réseau que Home Assistant** pour le push local.
- **WS69** : réseau 7-en-1 extérieur → **vent (vitesse/rafale/direction), pluie
  (taux + cumul), UV, luminosité (solaire W/m²)**, + sa propre temp/humidité
  (exposée au soleil → **on l'ignore** pour l'air).
- **WN32** : capteur temp/humidité abrité (boathouse) → **source primaire d'air
  et humidité** (`airb`/`humb`), meilleure que la véranda.

---

## 2. Modèle de données cible — `readings/{ms}`

Nouveaux champs **optionnels** (rétro-compat : le frontend gère leur absence).
Toutes les valeurs en **unités métriques**, arrondies comme indiqué.

| Champ  | Source        | Unité   | Notes |
|--------|---------------|---------|-------|
| `airb` | WN32          | °C      | air primaire (remplace la véranda dans `val('air')`) |
| `humb` | WN32          | %       | humidité primaire |
| `wind` | WS69          | km/h    | vitesse moyenne |
| `gust` | WS69          | km/h    | rafale |
| `wdir` | WS69          | °       | direction (0–360) — stockée, pas encore graphée |
| `rrate`| WS69          | mm/h    | taux de pluie instantané |
| `rday` | WS69          | mm      | **cumul du jour** (→ `val('rain')`) |
| `uv`   | WS69          | index   | 0–11+ |
| `solar`| WS69          | W/m²    | rayonnement solaire |
| `press`| GW3002 (baro) | hPa     | pression relative (au niveau mer) |

Les 5 mesures température/eau existantes (`air`, `surface`, `depth`, `airv`,
`hum`) restent inchangées. `airv`/`hum` (véranda) **restent écrites** comme
fallback — ne pas les retirer.

**Règles RTDB (`database.rules.json`) : AUCUN changement.** Lecture publique de
`readings`+`daily`, écriture réservée à l'uid writer. Rien à faire.

---

## 3. ÉTAPE BLOQUANTE — Config HA + noms d'entités (à faire AVANT le code)

L'intégration Ecowitt crée des entités dont les **noms exacts dépendent du nom
du device** dans HA. Il faut les capturer avant d'écrire le payload.

1. **Configurer l'intégration Ecowitt** dans HA
   (Settings → Devices & Services → Add Integration → **Ecowitt**). HA affiche
   un chemin/port webhook. Dans l'app **WSView Plus**, section
   **Customized / Weather Services**, pointer un push **local** vers
   `http://<IP_de_HA>:<port>` avec le protocole **Ecowitt**.
2. Régler les **unités en métrique** dans WSView Plus / l'intégration
   (km/h pour le vent, mm pour la pluie, hPa pour la pression) — sinon convertir
   dans les templates (mph→km/h ×1.609, in→mm ×25.4, inHg→hPa ×33.8639).
3. **Lister les entités créées** et me les donner. Commande PowerShell prête
   (lit le token depuis `backfill_veranda.py`, sans l'exposer) :

   ```powershell
   cd "D:\Claude desktop\ESPHome\manitou"
   $cfg = Get-Content backfill_veranda.py -Raw
   $url = [regex]::Match($cfg,'HA_URL\s*=\s*"([^"]+)"').Groups[1].Value
   $tok = [regex]::Match($cfg,'HA_TOKEN\s*=\s*"([^"]+)"').Groups[1].Value
   (Invoke-RestMethod "$url/api/states" -Headers @{Authorization="Bearer $tok"}) `
     | Where-Object { $_.entity_id -match 'wind|rain|uv|solar|pressure|gust|_wn32|ecowitt|gw3002' } `
     | Select-Object entity_id, state, @{n='unit';e={$_.attributes.unit_of_measurement}} `
     | Sort-Object entity_id | Format-Table -Auto
   ```

   Noms typiques de l'intégration Ecowitt (à confirmer avec la sortie ci-dessus) :
   `sensor.<device>_wind_speed`, `_wind_gust`, `_wind_direction`,
   `_rain_rate`, `_daily_rain_rate` (cumul jour), `_uv_index`,
   `_solar_radiation` (ou `_solar_lux`), `_relative_pressure`, et pour le WN32
   un canal temp/humidité distinct (`sensor.<wn32>_temperature` / `_humidity`).

---

## 4. Code Home Assistant — `home_assistant.yaml` (local, gitignored, contient secrets)

> ⚠️ Ce fichier contient des secrets (token HA, mot de passe writer Firebase).
> Ne jamais l'exposer/commiter. Il est déjà dans `.gitignore` + ignoré du hosting.

### 4a. Étendre le payload `manitou_firebase` (~ligne 33-44)

Ajouter les nouveaux champs. Remplacer `<...>` par les entités réelles de l'§3.
Garder `airv`/`hum` (fallback). Pattern défensif : `float(0)` évite un crash si
un capteur est momentanément `unavailable`, mais préférer un guard `null` pour
ne pas écrire des `0` trompeurs — utiliser un template conditionnel :

```yaml
  manitou_firebase:
    url: "https://lac-manitou-temperatures-d284a-default-rtdb.firebaseio.com/readings/{{ (now().timestamp() * 1000) | int }}.json?auth={{ token }}"
    method: PUT
    content_type: "application/json"
    payload: >-
      {% macro num(eid, dec=2) %}
        {%- set s = states(eid) -%}
        {%- if s in ['unknown','unavailable','none',''] or s is none -%}null
        {%- else -%}{{ s | float | round(dec) }}{%- endif -%}
      {% endmacro %}
      {
        "air":     {{ states('sensor.sondes_quai_lac_manitou_temperature_air')     | float(0) | round(2) }},
        "surface": {{ states('sensor.sondes_quai_lac_manitou_temperature_surface') | float(0) | round(2) }},
        "depth":   {{ states('sensor.sondes_quai_lac_manitou_temperature_4_pi')    | float(0) | round(2) }},
        "airv":    {{ states('sensor.remote_veranda_salle_a_manger_temperature')   | float(0) | round(2) }},
        "hum":     {{ states('sensor.remote_veranda_salle_a_manger_humidity')      | float(0) | round(2) }},
        "airb":    {{ num('sensor.<WN32>_temperature') }},
        "humb":    {{ num('sensor.<WN32>_humidity', 0) }},
        "wind":    {{ num('sensor.<WS69>_wind_speed', 1) }},
        "gust":    {{ num('sensor.<WS69>_wind_gust', 1) }},
        "wdir":    {{ num('sensor.<WS69>_wind_direction', 0) }},
        "rrate":   {{ num('sensor.<WS69>_rain_rate', 1) }},
        "rday":    {{ num('sensor.<WS69>_daily_rain_rate', 1) }},
        "uv":      {{ num('sensor.<WS69>_uv_index', 0) }},
        "solar":   {{ num('sensor.<WS69>_solar_radiation', 0) }},
        "press":   {{ num('sensor.<GW3002>_relative_pressure', 0) }}
      }
```

*(Si la macro pose problème dans le contexte `rest_command`, replier sur des
`states(...) | float(0)` simples comme les lignes existantes — mais alors un
capteur absent écrit `0`. La macro `num()` est préférable.)*

L'automation qui appelle `manitou_firebase` toutes les 5 min existe déjà et
fait le `firebase_signin` avant → **ne pas y toucher**.

### 4b. Étendre l'agrégation `/daily` — règles PAR MÉTRIQUE

C'est le point subtil : **toutes les mesures ne s'agrègent pas de la même façon.**

| Mesure | Règle d'agrégation quotidienne |
|--------|-------------------------------|
| air, surface, depth, airv, hum, airb, humb, press, uv, solar | **moyenne** |
| `rday` (pluie) | **max** du jour (c'est un cumul croissant → le max = total du jour) — **PAS la moyenne** |
| `wind` | **moyenne** |
| `gust` | **max** (rafale max du jour) → stocker en `gustmax` |

Deux fichiers à toucher :

1. **`firebase_put_daily`** (~ligne 57-61) — ajouter les champs au payload :
   ```yaml
   payload: '{"air": {{ air }}, "surface": {{ surface }}, "depth": {{ depth }}, "airv": {{ airv }}, "hum": {{ hum }}, "airb": {{ airb }}, "humb": {{ humb }}, "wind": {{ wind }}, "gustmax": {{ gustmax }}, "rday": {{ rday }}, "uv": {{ uv }}, "solar": {{ solar }}, "press": {{ press }}, "n": {{ n }}}'
   ```

2. **`manitou_aggregate_daily`** (~ligne 122-174) — ajouter les `data:` calculés,
   en suivant le pattern **selectattr-guarded** déjà utilisé pour `airv`/`hum`
   (indispensable : les jours d'avant l'installation n'ont pas ces champs) :
   ```yaml
                        airb: >-
                          {% set v = day.content.values() | selectattr('airb','defined') | map(attribute='airb') | map('float') | list %}
                          {{ (v | sum / (v | length)) | round(2) if v else 'null' }}
                        # … idem humb, wind, uv, solar, press (moyenne)
                        rday: >-
                          {% set v = day.content.values() | selectattr('rday','defined') | map(attribute='rday') | map('float') | list %}
                          {{ (v | max) | round(1) if v else 'null' }}
                        gustmax: >-
                          {% set v = day.content.values() | selectattr('gust','defined') | map(attribute='gust') | map('float') | list %}
                          {{ (v | max) | round(1) if v else 'null' }}
   ```

3. **Reconstruire `/daily`** une fois le script étendu (comme fait pour la
   véranda) : supprimer les jours à recalculer et relancer
   `script.manitou_aggregate_daily`. ⚠️ Ne supprimer que les jours **postérieurs
   à l'installation Ecowitt** — les jours antérieurs n'auront jamais ces champs,
   c'est normal (les tuiles météo afficheront `—` sur l'historique pré-install).

> Note : le frontend lit `/daily` sur les vues **saison/année**. Il lit `rday`
> pour la pluie via `val('rain')`. Pour le vent, il lit `wind`. `gustmax` n'est
> pas encore affiché — le stocker quand même pour plus tard.

---

## 5. Ajustements FRONTEND restants (`index.html`)

1. **Priorité air = WN32** : déjà géré ! `val('air')` fait déjà
   `airb ?? airv ?? air`. Rien à coder — vérifier juste qu'après branchement,
   la tuile Air affiche bien la valeur WN32 et non la véranda.

2. **Tendance pluie — cas spécial** (petit TODO connu) : `rday` est un cumul
   croissant, donc la flèche de tendance générique ↑/↓ n'a pas de sens. Attendu :
   afficher **« sec »** si `rday ≈ 0`, sinon le **taux `rrate` en mm/h** (ou le
   cumul du jour). Chercher `trendLabel` / la logique de rendu de la tuile pluie
   dans index.html et remplacer la flèche par ce texte pour la clé `rain`.

3. **Stats sous le graphique** (autre TODO connu) : `renderStats` (~ligne 1317)
   est codé en dur sur `['air','surface','depth','humidity']`. Optionnel : si on
   veut des stats Min/Moy/Max pour les nouvelles mesures quand elles sont
   sélectionnées, généraliser (mais décision UX non tranchée — voir PLAN.md
   « Questions ouvertes »). Peut être laissé pour plus tard.

---

## 6. Vérification (dans l'ordre)

1. **Forcer une écriture HA** : Developer Tools → Actions →
   `rest_command.firebase_signin` puis `rest_command.manitou_firebase`
   (ou attendre le prochain cycle 5 min). Vérifier `auth.status == 200`.
2. **Confirmer les champs dans Firebase** (PowerShell, lit la dernière lecture) :
   ```powershell
   $u = "https://lac-manitou-temperatures-d284a-default-rtdb.firebaseio.com/readings.json?orderBy=%22%24key%22&limitToLast=1"
   Invoke-RestMethod $u | ConvertTo-Json -Depth 5
   ```
   Attendu : `airb, humb, wind, gust, rday, uv, solar, press` présents et non nuls.
3. **Frontend** : `firebase hosting:channel:deploy rtdb-test --expires 7d`, puis
   ouvrir le canal de test **en navigation privée** (⚠️ le cache Hosting sert
   l'ancienne version — Ctrl+Shift+R insuffisant). Vérifier que les 5 tuiles
   météo s'allument, que le graphique bascule bien sur chaque mesure, et que
   24h/7j/30j affichent des courbes.
4. **`/daily`** : lancer `script.manitou_aggregate_daily`, vérifier que les
   nouveaux jours contiennent les agrégats, puis que les vues **saison/année**
   du graphique fonctionnent pour pluie/vent/etc.
5. **Go live** : quand tout est validé sur le canal de test →
   `firebase deploy --only hosting`.

---

## 7. Pièges connus (déjà rencontrés sur ce projet)

- **Cache Firebase Hosting** : toujours vérifier en **navigation privée**. Un
  hard-refresh ne suffit pas.
- **Token Firebase** : `idToken` valide ~1h. Le script `manitou_aggregate_daily`
  refait le `firebase_signin` à chaque run — OK. Le cycle 5 min aussi.
- **selectattr-guard obligatoire** : sans `selectattr('champ','defined')`, un
  seul jour/lecture sans le champ fait planter tout le calcul du bucket.
- **Conversions d'unités** : si l'intégration renvoie mph/in/inHg, convertir
  (×1.609 / ×25.4 / ×33.8639) — vérifier la colonne `unit` de la sortie §3.
- **Pluie = cumul, pas moyenne** : agréger `rday` par **max**, jamais moyenne.
- **Ne PAS intégrer `sensor.chalet_*`** (Honeywell) : analyse déjà faite, biais
  d'amortissement par le mur à l'emplacement #1. À réévaluer seulement après un
  éventuel déplacement au #2.

---

## 8. Fichiers de référence

| Fichier | Rôle |
|---------|------|
| `index.html` | frontend (val() ~881, RAW_PROP dans fetchData ~1063, renderStats ~1317, trendLabel) |
| `home_assistant.yaml` | **local/secrets** — rest_command `manitou_firebase` (~33), `firebase_put_daily` (~57), script `manitou_aggregate_daily` (~122) |
| `backfill_veranda.py` | **local/secrets** — source du HA_URL/HA_TOKEN pour les scripts d'inspection |
| `database.rules.json` | règles RTDB (inchangées) |
| `PLAN.md` | plan général + backlog (versionné) |
| `firebase.json` | hosting (ignore *.md, *.yaml, *.py) + ref règles DB |

RTDB : `https://lac-manitou-temperatures-d284a-default-rtdb.firebaseio.com/`
Canal test : `firebase hosting:channel:deploy rtdb-test --expires 7d`
