"""Estimation surface / 4 pieds pendant la panne (aperçu, aucune écriture)."""
import json, datetime as D, statistics as S, urllib.request, sys
sys.path.insert(0, r"D:\Claude desktop\ESPHome\recup")
import modele_lac as M

DAY = 86400000
first, last = 1789689600000, 1792627200000  # 2026-09-18 -> 2026-10-22 (UTC)
d = {k: v for k, v in M.days}

# ancres = jours avec mesures réelles : /daily (18, 21 sept.) + jours partiels du téléphone + 22 oct.
raw = json.load(open(r"D:\Claude desktop\ESPHome\recup\backfill_preview.json", encoding="utf-8"))["readings"]
today = json.load(urllib.request.urlopen(
    f'{M.RTDB}/readings.json?orderBy=%22$key%22&startAt=%22{last}%22&endAt=%22{last + DAY - 1}%22', timeout=60))
raw.update(today)
anchors = {}
for f in ("surface", "depth"):
    by = {}
    for k, v in raw.items():
        if v.get(f) is not None:
            by.setdefault((int(k) // DAY) * DAY, []).append(v[f])
    # 22 oct. = mesures réelles depuis le retour de l'ESP32 (quelques heures) : seuil abaissé
    anchors[f] = {k: (S.fmean(x), len(x)) for k, x in by.items() if len(x) >= (6 if k == last else 24)}
    for k in (first, first + 3 * DAY):  # 18 et 21 sept. déjà dans /daily
        if d.get(k, {}).get(f) is not None:
            anchors[f][k] = (d[k][f], d[k]["n"])

fmt = lambda k: D.datetime.utcfromtimestamp(k / 1000).strftime("%m-%d")
for f in ("surface", "depth"):
    params = M.fit(f, M.hist)[0]
    A = dict(sorted(anchors[f].items()))
    print(f"\n== {f} — ancres mesurées : " + "  ".join(f"{fmt(k)}:{v:.2f}(n={n})" for k, (v, n) in A.items()))
    ks = sorted(A)
    for a, b in zip(ks, ks[1:]):
        gap = (b - a) // DAY - 1
        if gap <= 0: continue
        forcing = [(d[a + j * DAY]["airb"], d[a + j * DAY]["solar"]) for j in range(gap + 1)]
        est = M.bridge(params, A[a][0], A[b][0], forcing)
        lin = [A[a][0] + (A[b][0] - A[a][0]) * (j + 1) / (gap + 1) for j in range(gap)]
        print(f"   trou {fmt(a)} -> {fmt(b)} ({gap} j)")
        for j, (e, l) in enumerate(zip(est, lin)):
            k = a + (j + 1) * DAY
            print(f"      {fmt(k)}  modèle {e:5.2f}  | ligne droite {l:5.2f}  | air {d[k]['airb']:5.1f}")
