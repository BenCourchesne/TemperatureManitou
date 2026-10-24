"""Variantes du modèle du lac (pas 24 h glissant) — validation croisée, aucune écriture.

Compare : air seul / air + soleil (modèle en prod) / air + soleil + humidité.
Mêmes tests que modele_horaire.py : trous cachés de 9 et 18 jours (été) + vraies heures
d'automne du téléphone cachées (1er-3 oct., 21-22 sept.). Recalage SANS la fenêtre testée.
"""
import json, statistics as S, collections, datetime as D

H = 3600
raw = json.load(open(r"D:\Claude desktop\ESPHome\recup\readings_all.json", encoding="utf-8"))
acc = collections.defaultdict(lambda: collections.defaultdict(list))
for k, v in raw.items():
    for f in ("surface", "depth", "airb", "solar", "humb"):
        if v.get(f) is not None:
            acc[int(k) // 1000 // H][f].append(v[f])
hours = {h: {f: S.fmean(x) for f, x in d.items()} for h, d in acc.items()}
DRIVERS = ("airb", "solar", "humb")
has = lambda h, f: f in hours.get(h, {})
forced = lambda h: all(has(h, f) for f in DRIVERS)

def mean24(h, key, w=None, field=None):
    xs = range(h, h + 24) if w is None else w
    return S.fmean(key(hours[x]) for x in xs)

# features(field, liste d'heures, niveau d'eau w) -> vecteur
VARIANTES = {
    "air seul":                lambda xs, w: [S.fmean(hours[x]["airb"] for x in xs) - w, 1.0],
    "air + soleil (prod)":     lambda xs, w: [S.fmean(hours[x]["airb"] for x in xs) - w,
                                              S.fmean(hours[x]["solar"] for x in xs) / 100, 1.0],
    "air + soleil + humidité": lambda xs, w: [S.fmean(hours[x]["airb"] for x in xs) - w,
                                              S.fmean(hours[x]["solar"] for x in xs) / 100,
                                              (100 - S.fmean(hours[x]["humb"] for x in xs)) / 10, 1.0],
}

def solve(X, y):
    n = len(X[0])
    M = [[sum(a[i] * a[j] for a in X) for j in range(n)] + [sum(a[i] * t for a, t in zip(X, y))] for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(M[r][i])); M[i], M[p] = M[p], M[i]
        for r in range(n):
            if r != i:
                f = M[r][i] / M[i][i]; M[r] = [a - f * b for a, b in zip(M[r], M[i])]
    return [M[i][n] / M[i][i] for i in range(n)]

SAMPLES = {}
def samples(field):
    if field not in SAMPLES:
        SAMPLES[field] = [h for h in hours if all(has(x, field) and forced(x) for x in range(h, h + 25))]
    return SAMPLES[field]

def fit(field, feat, exclude=()):
    X, y = [], []
    for h in samples(field):
        if any(x in exclude for x in range(h, h + 25)): continue
        xs = range(h, h + 24)
        X.append(feat(xs, S.fmean(hours[x][field] for x in xs)))
        y.append(hours[h + 24][field] - hours[h][field])
    return solve(X, y)

def bridge(coef, feat, field, h0, h1):
    w, pts, h = hours[h0][field], {h0: hours[h0][field]}, h0
    while h < h1:
        end = min(h + 24, h1)
        xs = [x for x in range(h, end) if forced(x)]
        if not xs: return None
        w = w + (end - h) / 24 * sum(c * f for c, f in zip(coef, feat(xs, w)))
        h = end; pts[h] = w
    err = hours[h1][field] - pts[h1]; ks = sorted(pts); out = {}
    for x in range(h0 + 1, h1):
        a = max(t for t in ks if t <= x); z = min(t for t in ks if t > x)
        out[x] = pts[a] + (pts[z] - pts[a]) * (x - a) / (z - a) + err * (x - h0) / (h1 - h0)
    return out

def daily_err(est, truth):
    be, bt = collections.defaultdict(list), collections.defaultdict(list)
    for h, e in est.items():
        if h in truth: be[h // 24].append(e); bt[h // 24].append(truth[h])
    return [abs(S.fmean(be[d]) - S.fmean(bt[d])) for d in be if len(be[d]) >= 20]

PANNE_H = 1789689600 // H
q = lambda e: f"{S.fmean(e):.2f} °C" if e else "—"
for field in ("surface", "depth"):
    print(f"\n== {field}")
    known = sorted(h for h in hours if has(h, field) and forced(h) and h < PANNE_H)
    for name, feat in VARIANTES.items():
        res = []
        for gap in (9, 18):
            errs = []
            for start in range(known[0], known[-1] - (gap + 2) * 24, 48):
                h0, h1 = start, start + (gap + 1) * 24
                if not (has(h0, field) and has(h1, field)): continue
                win = set(range(h0 + 1, h1))
                truth = {h: hours[h][field] for h in win if has(h, field)}
                if len(truth) < 0.6 * len(win): continue
                est = bridge(fit(field, feat, win), feat, field, h0, h1)
                if est: errs += daily_err(est, truth)
            res.append(f"trou {gap} j : {q(errs)}")
        for label, a, b in (("1er-3 oct.", D.datetime(2026, 10, 1), D.datetime(2026, 10, 4, 12)),
                            ("21-22 sept.", D.datetime(2026, 9, 20, 22), D.datetime(2026, 10, 1, 21))):
            a_h = int(a.replace(tzinfo=D.timezone.utc).timestamp()) // H
            b_h = int(b.replace(tzinfo=D.timezone.utc).timestamp()) // H
            h0 = max(h for h in hours if has(h, field) and h <= a_h)
            h1 = min(h for h in hours if has(h, field) and h >= b_h)
            win = set(range(h0 + 1, h1))
            truth = {h: hours[h][field] for h in win if has(h, field)}
            est = bridge(fit(field, feat, win), feat, field, h0, h1)
            res.append(f"automne {label} : {S.fmean(abs(est[h] - truth[h]) for h in truth):.2f} °C")
        coef = [round(c, 3) for c in fit(field, feat)]
        print(f"   {name:24s} | " + " | ".join(res) + f" | coefs {coef}")
