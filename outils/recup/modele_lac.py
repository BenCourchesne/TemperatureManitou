"""Modèle de température du lac (surface, 4 pieds) piloté par l'air de la station météo.

Pas de temps = 1 jour (moyennes /daily). Modèle de relaxation :
    W[t+1] = W[t] + k * (A[t] - W[t]) + b * solaire[t]/100 + c
calé par moindres carrés sur l'historique d'AVANT la panne, puis validé en
« faisant semblant » de perdre des fenêtres connues de 9 et 18 jours.
Aucune écriture : ce script ne fait que lire et calculer.
"""
import json, sys, datetime as D, statistics as S, urllib.request

RTDB = "https://lac-manitou-temperatures-d284a-default-rtdb.firebaseio.com"
PANNE = 1789689600000  # 2026-09-18 00:00 UTC : tout ce qui précède sert au calage
daily = json.load(urllib.request.urlopen(f"{RTDB}/daily.json", timeout=60))
days = sorted((int(k), v) for k, v in daily.items())
hist = [(k, v) for k, v in days if k < PANNE and v.get("airb") is not None and v.get("solar") is not None]

def series(field, data):
    """listes alignées de jours consécutifs : (W, A, sol) ; None si trou"""
    return [(v.get(field), v["airb"], v["solar"]) for _, v in data]

def fit(field, data):
    rows = []
    for (k0, v0), (k1, v1) in zip(data, data[1:]):
        if k1 - k0 != 86400000: continue
        if v0.get(field) is None or v1.get(field) is None: continue
        rows.append((v0["airb"] - v0[field], v0["solar"] / 100, 1.0, v1[field] - v0[field]))
    # moindres carrés 3x3 (équations normales)
    X = [r[:3] for r in rows]; y = [r[3] for r in rows]
    XtX = [[sum(a[i] * a[j] for a in X) for j in range(3)] for i in range(3)]
    Xty = [sum(a[i] * t for a, t in zip(X, y)) for i in range(3)]
    # résolution Gauss
    M = [XtX[i] + [Xty[i]] for i in range(3)]
    for i in range(3):
        p = max(range(i, 3), key=lambda r: abs(M[r][i])); M[i], M[p] = M[p], M[i]
        for r in range(3):
            if r != i:
                f = M[r][i] / M[i][i]
                M[r] = [a - f * b for a, b in zip(M[r], M[i])]
    k, b, c = (M[i][3] / M[i][i] for i in range(3))
    resid = [t - (k * a[0] + b * a[1] + c) for a, t in zip(X, y)]
    return (k, b, c), len(rows), S.pstdev(resid)

def simulate(params, w0, forcing):
    k, b, c = params
    out, w = [], w0
    for a, sol in forcing:
        w = w + k * (a - w) + b * sol / 100 + c
        out.append(w)
    return out

def bridge(params, w_start, w_end, forcing):
    """simule entre deux ancres puis répartit linéairement l'écart final"""
    sim = simulate(params, w_start, forcing)       # sim[i] = jour start+1+i ; dernier = jour de l'ancre de fin
    err = w_end - sim[-1]
    n = len(sim)
    return [s + err * (i + 1) / n for i, s in enumerate(sim)][:-1]

def validate(field, params, data, gap):
    """pour chaque fenêtre possible : ancre au jour 0 et au jour gap+1, estime les gap jours du milieu"""
    vals = {k: v for k, v in data}
    keys = [k for k, _ in data]
    e_model, e_lin, e_free = [], [], []
    for i, k0 in enumerate(keys):
        ks = [k0 + j * 86400000 for j in range(gap + 2)]
        if not all(x in vals and vals[x].get(field) is not None for x in ks): continue
        truth = [vals[x][field] for x in ks]
        forcing = [(vals[x]["airb"], vals[x]["solar"]) for x in ks[:-1]]
        est = bridge(params, truth[0], truth[-1], forcing)
        lin = [truth[0] + (truth[-1] - truth[0]) * (j + 1) / (gap + 1) for j in range(gap)]
        free = simulate(params, truth[0], forcing)[:-1]
        mid = truth[1:-1]
        e_model += [abs(a - b) for a, b in zip(est, mid)]
        e_lin += [abs(a - b) for a, b in zip(lin, mid)]
        e_free += [abs(a - b) for a, b in zip(free, mid)]
    q = lambda e: f"moy {S.fmean(e):.2f} °C | 90 % < {sorted(e)[int(.9 * len(e))]:.2f} | max {max(e):.2f}"
    return len(e_model) // gap, q(e_model), q(e_lin), q(e_free)

if __name__ == "__main__":
    print(f"Calage sur {len(hist)} jours avant la panne "
          f"({D.datetime.utcfromtimestamp(hist[0][0]/1000):%Y-%m-%d} -> {D.datetime.utcfromtimestamp(hist[-1][0]/1000):%Y-%m-%d})\n")
    for field in ("surface", "depth"):
        params, n, sd = fit(field, hist)
        k, b, c = params
        print(f"== {field} : k={k:.3f}/jour (rattrape {k*100:.0f} % de l'écart air-eau par jour), "
              f"solaire b={b:.3f}, c={c:+.3f} | {n} paires, bruit jour-à-jour {sd:.2f} °C")
        for gap in (9, 18):
            nw, m, l, f = validate(field, params, hist, gap)
            print(f"   trou de {gap:2d} jours ({nw} fenêtres testées)")
            print(f"      modèle + ancres : {m}")
            print(f"      ligne droite    : {l}")
            print(f"      modèle sans ancre de fin : {f}")
