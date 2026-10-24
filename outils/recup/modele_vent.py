"""Comparaison de modèles du lac avec / sans vent — validation croisée (aucune écriture).

Variante générique : W[t+1] - W[t] = somme(coef_i * feature_i(jour t))
Chaque fenêtre testée est retirée du calage avant d'être estimée (pas de triche).
"""
import json, statistics as S, urllib.request, datetime as D

RTDB = "https://lac-manitou-temperatures-d284a-default-rtdb.firebaseio.com"
PANNE = 1789689600000
DAY = 86400000
daily = json.load(urllib.request.urlopen(f"{RTDB}/daily.json", timeout=60))
hist = {int(k): v for k, v in daily.items()
        if int(k) < PANNE and all(v.get(f) is not None for f in ("airb", "solar", "wind"))}

VARIANTES = {
    "air seul":             lambda w, v: [v["airb"] - w, v["solar"] / 100, 1],
    "air + vent (échange)": lambda w, v: [v["airb"] - w, v["wind"] * (v["airb"] - w) / 10, v["solar"] / 100, 1],
    "air + vent (rafales)": lambda w, v: [v["airb"] - w, v["gustmax"] * (v["airb"] - w) / 10, v["solar"] / 100, 1],
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

def fit(field, feat, exclude=()):
    X, y = [], []
    for k, v in hist.items():
        n = hist.get(k + DAY)
        if n is None or k in exclude or k + DAY in exclude: continue
        if v.get(field) is None or n.get(field) is None or v.get("gustmax") is None: continue
        X.append(feat(v[field], v)); y.append(n[field] - v[field])
    return solve(X, y)

def step(coef, feat, w, v):
    return w + sum(c * x for c, x in zip(coef, feat(w, v)))

def bridge(coef, feat, w0, w1, forc):
    sim, w = [], w0
    for v in forc:
        w = step(coef, feat, w, v); sim.append(w)
    err = w1 - sim[-1]; n = len(sim)
    return [s + err * (i + 1) / n for i, s in enumerate(sim)][:-1]

def test(field, feat, gap):
    errs = []
    for k0 in sorted(hist):
        ks = [k0 + j * DAY for j in range(gap + 2)]
        if not all(x in hist and hist[x].get(field) is not None and hist[x].get("gustmax") is not None for x in ks):
            continue
        coef = fit(field, feat, exclude=set(ks))
        truth = [hist[x][field] for x in ks]
        est = bridge(coef, feat, truth[0], truth[-1], [hist[x] for x in ks[:-1]])
        errs += [abs(a - b) for a, b in zip(est, truth[1:-1])]
    return errs

def test_lin(field, gap):
    errs = []
    for k0 in sorted(hist):
        ks = [k0 + j * DAY for j in range(gap + 2)]
        if not all(x in hist and hist[x].get(field) is not None and hist[x].get("gustmax") is not None for x in ks):
            continue
        t = [hist[x][field] for x in ks]
        errs += [abs(t[0] + (t[-1] - t[0]) * (j + 1) / (gap + 1) - t[j + 1]) for j in range(gap)]
    return errs

q = lambda e: f"moy {S.fmean(e):.2f} | 90 % < {sorted(e)[int(.9 * len(e))]:.2f} | max {max(e):.2f}"
print(f"Calage : {len(hist)} jours avant la panne, validation croisée\n")
for field in ("surface", "depth"):
    print(f"== {field}")
    for gap in (9, 18):
        print(f"   trou de {gap} jours")
        print(f"      {'ligne droite':22s} {q(test_lin(field, gap))}")
        for name, feat in VARIANTES.items():
            print(f"      {name:22s} {q(test(field, feat, gap))}")
    for name, feat in VARIANTES.items():
        print(f"   coefficients {name}: {[round(c, 4) for c in fit(field, feat)]}")
