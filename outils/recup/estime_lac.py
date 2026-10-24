"""Estimation de la température du lac (surface, 4 pieds) pour les jours de panne sans mesures.

Modèle (validé le 2026-10-22, voir modele_horaire.py) — pas de 24 h, fenêtres glissantes :
    W[h+24] - W[h] = k * moy24(Air - W) + b * moy24(solaire)/100 + c
Air = station météo (airb), complète pendant la panne. Le modèle est recalé sur TOUTES les
heures où l'eau et l'air sont mesurés, puis chaque trou est « ponté » entre deux ancres
mesurées (moyenne des 6 heures réelles au bord du trou) et l'écart final est réparti
linéairement : l'estimation passe toujours par les vraies mesures.

Règles d'écriture dans /daily (jours UTC du 2026-09-18 au 2026-10-21) :
  - jour avec ≥ 18 h de mesures réelles du lac -> moyenne des vraies mesures, AUCUNE marque
  - sinon -> moyenne sur 24 h (heures réelles + heures estimées), est: 1
  /readings n'est jamais touché. Les autres champs de /daily (météo) sont conservés (PATCH).

Ré-exécutable : quand il y aura plus de jours d'automne, relancer -> recalage -> réécriture
des mêmes jours. Les paramètres utilisés sont écrits dans estime_lac_params.json.

  python estime_lac.py            -> aperçu (rafraîchir readings_all.json avant si besoin)
  python estime_lac.py --ecrire   -> mot de passe ha-writer, écrit /daily
"""
import json, sys, getpass, statistics as S, collections, datetime as D, urllib.request, urllib.parse, urllib.error

HERE = r"D:\Claude desktop\ESPHome\recup"
RTDB = "https://lac-manitou-temperatures-d284a-default-rtdb.firebaseio.com"
API_KEY = "AIzaSyANzIvc-kAmlLyn7wxdpyPSsRFNNmwXulY"
WRITER = "ha-writer@manitou.local"
H, DAY_MS = 3600, 86400000
FIRST_DAY, LAST_DAY = 1789689600000, 1792540800000   # 2026-09-18 .. 2026-10-21 (UTC)
MIN_REAL_H = 18    # heures réelles du lac (sur 24) pour qu'un jour soit « mesuré »
ANCHOR_H = 6       # heures réelles moyennées pour chaque ancre
FIELDS = ("surface", "depth")

raw = json.load(open(f"{HERE}\\readings_all.json", encoding="utf-8"))
acc = collections.defaultdict(lambda: collections.defaultdict(list))
for k, v in raw.items():
    for f in FIELDS + ("airb", "solar"):
        if v.get(f) is not None:
            acc[int(k) // 1000 // H][f].append(v[f])
hours = {h: {f: S.fmean(x) for f, x in d.items()} for h, d in acc.items()}
has = lambda h, f: f in hours.get(h, {})
forced = lambda h: has(h, "airb") and has(h, "solar")

def fit(field):
    X, y = [], []
    for h in hours:
        span = range(h, h + 25)
        if not all(has(x, field) and forced(x) for x in span): continue
        X.append((S.fmean(hours[x]["airb"] - hours[x][field] for x in range(h, h + 24)),
                  S.fmean(hours[x]["solar"] for x in range(h, h + 24)) / 100, 1.0))
        y.append(hours[h + 24][field] - hours[h][field])
    M = [[sum(a[i] * a[j] for a in X) for j in range(3)] + [sum(a[i] * t for a, t in zip(X, y))] for i in range(3)]
    for i in range(3):
        p = max(range(i, 3), key=lambda r: abs(M[r][i])); M[i], M[p] = M[p], M[i]
        for r in range(3):
            if r != i:
                f = M[r][i] / M[i][i]; M[r] = [a - f * b for a, b in zip(M[r], M[i])]
    return [M[i][3] / M[i][i] for i in range(3)], len(X)

def bridge(coef, h0, w0, h1, w1):
    """trajectoire horaire de h0+1 à h1-1, partant de w0 et recollée sur w1"""
    k, b, c = coef
    w, pts, h = w0, {h0: w0}, h0
    while h < h1:
        end = min(h + 24, h1)
        seg = [x for x in range(h, end) if forced(x)]
        A = S.fmean(hours[x]["airb"] for x in seg); sol = S.fmean(hours[x]["solar"] for x in seg) / 100
        w = w + (end - h) / 24 * (k * (A - w) + b * sol + c)
        h = end; pts[h] = w
    err = w1 - pts[h1]; ks = sorted(pts); out = {}
    for x in range(h0 + 1, h1):
        a = max(t for t in ks if t <= x); z = min(t for t in ks if t > x)
        out[x] = pts[a] + (pts[z] - pts[a]) * (x - a) / (z - a) + err * (x - h0) / (h1 - h0)
    return out

def diurnal(field, since_h):
    """cycle jour/nuit moyen : écart de chaque heure (UTC) à la moyenne centrée sur 24 h"""
    dev = collections.defaultdict(list)
    for h in hours:
        if h < since_h or not has(h, field): continue
        win = range(h - 12, h + 12)
        if all(has(x, field) for x in win):
            dev[h % 24].append(hours[h][field] - S.fmean(hours[x][field] for x in win))
    return {hod: S.fmean(dev[hod]) if dev[hod] else 0.0 for hod in range(24)}

DIURNAL_SINCE = 1787184000 // H   # 2026-08-20 : fin d'été + automne (cycle plus faible qu'en juillet)
lo_h, hi_h = FIRST_DAY // 1000 // H, (LAST_DAY + DAY_MS) // 1000 // H
fmt_d = lambda ms: D.datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d")
params, est_hours, gaps_log = {}, {}, []
for field in FIELDS:
    coef, n = fit(field)
    params[field] = {"k": coef[0], "b": coef[1], "c": coef[2], "fenetres_24h": n}
    prof = diurnal(field, DIURNAL_SINCE)
    params[field]["cycle_jour_amplitude"] = round(max(prof.values()) - min(prof.values()), 2)
    known = sorted(h for h in hours if has(h, field))
    est = {}
    for h0, h1 in zip(known, known[1:]):
        if h1 - h0 <= 1 or h1 < lo_h or h0 > hi_h: continue
        # ancres « désaisonnalisées » (cycle jour/nuit retiré) : le modèle raisonne en moyennes 24 h
        a = [hours[x][field] - prof[x % 24] for x in known if h0 - 48 < x <= h0][-ANCHOR_H:]
        z = [hours[x][field] - prof[x % 24] for x in known if h1 <= x < h1 + 48][:ANCHOR_H]
        traj = bridge(coef, h0, S.fmean(a), h1, S.fmean(z))
        est.update({h: w + prof[h % 24] for h, w in traj.items()})
        if h1 - h0 > 24:
            gaps_log.append((field, h0, h1))
    est_hours[field] = est

# lectures réelles du lac par jour UTC
real = collections.defaultdict(lambda: collections.defaultdict(list))
for k, v in raw.items():
    for f in FIELDS:
        if v.get(f) is not None:
            real[(int(k) // DAY_MS) * DAY_MS][f].append(v[f])

current = json.load(urllib.request.urlopen(
    f'{RTDB}/daily.json?orderBy=%22$key%22&startAt=%22{FIRST_DAY}%22&endAt=%22{LAST_DAY}%22', timeout=60))
plan = {}
for dk in range(FIRST_DAY, LAST_DAY + 1, DAY_MS):
    hrs = range(dk // 1000 // H, dk // 1000 // H + 24)
    out = {}
    for f in FIELDS:
        r = real[dk][f]
        real_hours = sum(1 for h in hrs if has(h, f))
        if real_hours >= MIN_REAL_H:
            out[f] = round(S.fmean(r), 2)
        else:
            # jour partiel ou vide : heures réelles là où elles existent, modèle ailleurs
            # (évite le biais d'une moyenne faite seulement sur l'après-midi)
            vals = [hours[h][f] if has(h, f) else est_hours[f].get(h) for h in hrs]
            vals = [v for v in vals if v is not None]
            out[f] = round(S.fmean(vals), 2) if len(vals) >= 20 else None
            out["est"] = 1
    plan[str(dk)] = out

print("Modèle recalé sur toutes les données disponibles :")
for f, p in params.items():
    print(f"   {f:8s} k={p['k']*100:.1f} %/jour  b={p['b']:+.3f}  c={p['c']:+.3f}  ({p['fenetres_24h']} fenêtres de 24 h)"
          f"  | cycle jour/nuit {p['cycle_jour_amplitude']:.2f} °C")
print("\nTrous pontés (> 24 h) :")
for f, h0, h1 in gaps_log:
    print(f"   {f:8s} {D.datetime.utcfromtimestamp(h0*H):%m-%d %Hh} -> {D.datetime.utcfromtimestamp(h1*H):%m-%d %Hh} UTC ({(h1-h0)/24:.1f} j)")
print("\n jour        type     surface  4 pieds | actuel /daily  surf  4pi |  air station")
for dk, o in plan.items():
    cur = current.get(dk, {})
    s = lambda x: f"{x:6.2f}" if x is not None else "     —"
    print(f" {fmt_d(int(dk))}  {'ESTIMÉ ' if o.get('est') else 'mesuré '}  {s(o['surface'])}  {s(o['depth'])}  |"
          f"            {s(cur.get('surface'))} {s(cur.get('depth'))} |  {s(cur.get('airb'))}")

params_out = {"calé_le": D.datetime.now().isoformat(timespec="minutes"), "modele": "pas 24 h glissant, air=airb",
              "ancre_heures": ANCHOR_H, "min_heures_jour_mesure": MIN_REAL_H, "parametres": params,
              "jours_estimes": [fmt_d(int(k)) for k, o in plan.items() if o.get("est")]}
json.dump(params_out, open(f"{HERE}\\estime_lac_params.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

if "--ecrire" not in sys.argv:
    print("\nAPERÇU seulement — rien n'a été écrit. Pour écrire : python estime_lac.py --ecrire")
    sys.exit(0)

token = None
for _ in range(3):
    pwd = getpass.getpass(f"\nMot de passe Firebase de {WRITER} (non affiché) : ").strip()
    req = urllib.request.Request(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}",
        data=json.dumps({"email": WRITER, "password": pwd, "returnSecureToken": True}).encode(),
        headers={"Content-Type": "application/json"})
    try:
        token = json.load(urllib.request.urlopen(req, timeout=30))["idToken"]; print("  Connexion Firebase OK"); break
    except urllib.error.HTTPError as e:
        print(f"  Connexion refusée : {json.load(e).get('error', {}).get('message', '?')}")
    finally:
        del pwd
if not token:
    sys.exit("Abandon — rien n'a été écrit.")

# PATCH multi-chemins : seuls surface/depth/est de chaque jour sont touchés (est: null retire la marque)
body = {}
for dk, o in plan.items():
    for f in FIELDS:
        body[f"{dk}/{f}"] = o[f]
    body[f"{dk}/est"] = o.get("est")
r = urllib.request.Request(f"{RTDB}/daily.json?auth={token}", data=json.dumps(body).encode(), method="PATCH",
                           headers={"Content-Type": "application/json"})
urllib.request.urlopen(r, timeout=120).read()
print(f"  /daily : {len(plan)} jours mis à jour ({sum(1 for o in plan.values() if o.get('est'))} estimés). Terminé.")
