"""Modèle HORAIRE du lac calé sur toutes les lectures disponibles (aucune écriture).

    W[h+1] - W[h] = k * (Air[h] - W[h]) + b * solaire[h]/100 + c

Air = station météo (airb). Validation croisée : on cache des fenêtres de 9 et 18 jours,
on recale sans elles, on estime heure par heure entre la dernière heure connue avant et la
première après, puis on compare les MOYENNES QUOTIDIENNES estimées aux vraies.
Test d'automne : on cache les vraies mesures du téléphone des 1er-3 oct. (et 21-22 sept.).
"""
import json, statistics as S, collections, datetime as D

H = 3600
raw = json.load(open(r"D:\Claude desktop\ESPHome\recup\readings_all.json", encoding="utf-8"))

# moyennes horaires
acc = collections.defaultdict(lambda: collections.defaultdict(list))
for k, v in raw.items():
    h = int(k) // 1000 // H
    for f in ("surface", "depth", "airb", "solar"):
        if v.get(f) is not None:
            acc[h][f].append(v[f])
hours = {h: {f: S.fmean(x) for f, x in d.items()} for h, d in acc.items()}
print(f"{len(hours)} heures avec données ({sum(1 for v in hours.values() if 'surface' in v and 'airb' in v)} avec eau + air)")

def ok(h, field):
    v = hours.get(h)
    return v is not None and field in v and "airb" in v and "solar" in v

def fit(field, exclude=()):
    """pas de 24 h, fenêtres glissantes heure par heure : W[h+24]-W[h] = k*moy(A-W) + b*moy(sol)/100 + c"""
    X, y = [], []
    for h, v in hours.items():
        span = range(h, h + 25)
        if any(x in exclude for x in span) or not all(ok(x, field) for x in span): continue
        gap = S.fmean(hours[x]["airb"] - hours[x][field] for x in range(h, h + 24))
        sol = S.fmean(hours[x]["solar"] for x in range(h, h + 24)) / 100
        X.append((gap, sol, 1.0)); y.append(hours[h + 24][field] - v[field])
    n = 3
    M = [[sum(a[i] * a[j] for a in X) for j in range(n)] + [sum(a[i] * t for a, t in zip(X, y))] for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(M[r][i])); M[i], M[p] = M[p], M[i]
        for r in range(n):
            if r != i:
                f = M[r][i] / M[i][i]; M[r] = [a - f * b for a, b in zip(M[r], M[i])]
    return [M[i][n] / M[i][i] for i in range(n)], len(X)

def bridge(coef, field, h0, h1):
    """pas de 24 h depuis h0 (forçage = moyenne sur 24 h), interpolé à l'heure, recollé sur h1"""
    k, b, c = coef
    w, pts, h = hours[h0][field], {h0: hours[h0][field]}, h0
    while h < h1:
        end = min(h + 24, h1)
        seg = [x for x in range(h, end) if "airb" in hours.get(x, {}) and "solar" in hours.get(x, {})]
        if not seg: return None
        A = S.fmean(hours[x]["airb"] for x in seg); sol = S.fmean(hours[x]["solar"] for x in seg) / 100
        w = w + (end - h) / 24 * (k * (A - w) + b * sol + c)
        h = end; pts[h] = w
    err = hours[h1][field] - pts[h1]
    ks, out = sorted(pts), {}
    for x in range(h0 + 1, h1):
        a = max(t for t in ks if t <= x); z = min(t for t in ks if t > x)
        out[x] = pts[a] + (pts[z] - pts[a]) * (x - a) / (z - a) + err * (x - h0) / (h1 - h0)
    return out

def daily_err(field, est, truth_hours):
    """écart entre moyennes quotidiennes estimées et vraies (jours UTC entièrement dans la fenêtre)"""
    by_e, by_t = collections.defaultdict(list), collections.defaultdict(list)
    for h, e in est.items():
        if h in truth_hours:
            by_e[h // 24].append(e); by_t[h // 24].append(truth_hours[h])
    return [abs(S.fmean(by_e[d]) - S.fmean(by_t[d])) for d in by_e if len(by_e[d]) >= 20]

q = lambda e: "aucune fenêtre testable" if not e else f"moy {S.fmean(e):.2f} °C | 90 % < {sorted(e)[int(.9 * len(e))]:.2f} | max {max(e):.2f}  ({len(e)} jours)"
PANNE_H = 1789689600 // H
for field in ("surface", "depth"):
    coef, n = fit(field)
    print(f"\n== {field} : k={coef[0]*100:.1f} %/jour, b={coef[1]:.4f}, c={coef[2]:+.4f} | {n} fenêtres de 24 h")
    known = sorted(h for h in hours if ok(h, field) and h < PANNE_H)
    for gap_days in (9, 18):
        em, el = [], []
        for start in range(known[0], known[-1] - (gap_days + 2) * 24, 24 * 2):  # une fenêtre tous les 2 jours
            h0, h1 = start, start + (gap_days + 1) * 24
            if not (ok(h0, field) and ok(h1, field)): continue
            win = set(range(h0 + 1, h1))
            truth = {h: hours[h][field] for h in win if ok(h, field)}
            if len(truth) < 0.6 * len(win): continue
            c2, _ = fit(field, exclude=win)
            est = bridge(c2, field, h0, h1)
            if est is None: continue
            lin = {h: hours[h0][field] + (hours[h1][field] - hours[h0][field]) * (h - h0) / (h1 - h0) for h in est}
            em += daily_err(field, est, truth); el += daily_err(field, lin, truth)
        print(f"   trou de {gap_days} jours | modèle horaire : {q(em)}")
        print(f"   {'':16s}| ligne droite   : {q(el)}")

    # test d'automne sur les vraies mesures du téléphone
    for label, a, b in (("cache 1er-3 oct.", D.datetime(2026, 10, 1, 0), D.datetime(2026, 10, 4, 12)),
                        ("cache 21-22 sept.", D.datetime(2026, 9, 20, 22), D.datetime(2026, 10, 1, 21))):
        a_h = int(a.replace(tzinfo=D.timezone.utc).timestamp()) // H
        b_h = int(b.replace(tzinfo=D.timezone.utc).timestamp()) // H
        h0 = max(h for h in hours if ok(h, field) and h <= a_h)
        h1 = min(h for h in hours if ok(h, field) and h >= b_h)
        win = set(range(h0 + 1, h1))
        truth = {h: hours[h][field] for h in win if ok(h, field)}
        c2, _ = fit(field, exclude=win)
        est = bridge(c2, field, h0, h1)
        lin = {h: hours[h0][field] + (hours[h1][field] - hours[h0][field]) * (h - h0) / (h1 - h0) for h in est}
        em = [abs(est[h] - truth[h]) for h in truth]; el = [abs(lin[h] - truth[h]) for h in truth]
        bias = S.fmean(est[h] - truth[h] for h in truth)
        print(f"   AUTOMNE {label:18s}: {len(truth)} h réelles cachées | modèle moy {S.fmean(em):.2f} °C (biais {bias:+.2f})"
              f" | ligne droite moy {S.fmean(el):.2f} °C")
