"""Rattrapage de la panne du quai (2026-09-18 -> 2026-10-22) vers Firebase /readings + /daily.

Sources (dans ce dossier) :
  gw3000/202609A.csv, 202610A.csv   -> bien datés
  gw3000/202412A.csv, 202501A.csv   -> horloge remise au 2024-12-31 20:01 à chaque reboot sans NTP,
                                       recalés segment par segment (midi solaire + pression EC Mont-Tremblant)
  esp32.jsonl                       -> sondes du lac captées par le téléphone (air/surface/depth)

Usage :
  python backfill.py            -> APERÇU : écrit backfill_preview.json, n'envoie RIEN à Firebase
  python backfill.py --ecrire   -> demande le mot de passe ha-writer, écrit /readings puis /daily,
                                   et retire les faux 0.0 de la véranda (airv/hum) depuis le retour du lien
Ré-exécutable sans risque : mêmes clés -> mêmes valeurs (idempotent).
"""
import csv, json, math, sys, bisect, getpass, collections, datetime as D, urllib.request, urllib.parse, urllib.error

HERE = r"D:\Claude desktop\ESPHome\recup"
RTDB = "https://lac-manitou-temperatures-d284a-default-rtdb.firebaseio.com"
API_KEY = "AIzaSyANzIvc-kAmlLyn7wxdpyPSsRFNNmwXulY"  # même clé que cp.html (l'ancienne AIzaSyCV… a expiré)
WRITER = "ha-writer@manitou.local"
EDT = D.timezone(D.timedelta(hours=-4))
UTC = D.timezone.utc
WRITE = "--ecrire" in sys.argv

# ─────────────────────────────── 1. lectures GW3000 recalées ────────────────────────────────
# Décalage = début réel de chaque segment. Mesurés par midi solaire (A, C) et corrigés par la
# pression de la station EC Mont-Tremblant (B2, +38 min). S1 (11 pts), B1 (6 pts), Z (1 pt) et
# le mini-reboot de 2 lignes avant C : trop courts pour être placés de façon fiable -> ignorés.
def load(f):
    return list(csv.DictReader(open(f"{HERE}\\gw3000\\{f}", encoding="utf-8-sig")))
dec, jan = load("202412A.csv"), load("202501A.csv")
SEGMENTS = [
    ("sept", load("202609A.csv"), None),
    ("A", dec[11:59] + jan[0:3112], D.datetime(2026, 9, 20, 17, 32, tzinfo=EDT)),
    ("B2", dec[65:113] + jan[3112:3554], D.datetime(2026, 10, 1, 17, 22, tzinfo=EDT)),
    ("C", dec[115:163] + jan[3554:], D.datetime(2026, 10, 3, 12, 57, 58, tzinfo=EDT)),
    ("oct", load("202610A.csv"), None),
]

f2c = lambda v: round((float(v) - 32) / 1.8, 1)
mph = lambda v: round(float(v) * 1.609344, 1)
inch = lambda v: float(v) * 25.4
num = lambda v: v not in ("--", "", None)

rows = []
for name, seg, real_start in SEGMENTS:
    back = [i for i in range(1, len(seg)) if int(seg[i]["Timestamp"]) <= int(seg[i - 1]["Timestamp"])]
    assert not back, f"segment {name} : saut d'horloge arrière à la ligne {back[0]} — à traiter avant d'écrire"
    off = 0 if real_start is None else real_start.timestamp() - int(seg[0]["Timestamp"])
    prev_m = None
    for r in seg:
        m = float(r["Monthly Rain(in)"]) if num(r["Monthly Rain(in)"]) else None
        inc = 0.0
        if m is not None and prev_m is not None:
            inc = m - prev_m if m >= prev_m else m  # remise à 0 du compteur mensuel
        prev_m = m
        g = lambda col, fn: fn(r[col]) if num(r[col]) else None
        rows.append({
            "t": int(r["Timestamp"]) + off, "seg": name, "rain_inc_mm": inch(inc),
            "airb": g("Outdoor Temperature(°F)", f2c),
            "humb": g("Outdoor Humidity(%)", int),
            "press": g("REL Pressure(inHg)", lambda v: round(float(v) * 33.8639, 1)),
            "wind": g("Wind(mph)", mph),
            "gust": g("Gust(mph)", mph),
            "wdir": g("Wind Direction(deg)", int),
            "solar": g("Solar Rad(W/m2)", lambda v: round(float(v))),
            "uv": g("UV-Index", lambda v: int(float(v))),
            "rrate": g("Rain Rate(in/Hr)", lambda v: round(inch(v), 1)),
        })
rows.sort(key=lambda r: r["t"])

# ──────────────────── 2. fenêtre = strictement entre la dernière lecture avant panne et la 1re après
def get(path, **q):
    url = f"{RTDB}/{path}.json" + ("?" + urllib.parse.urlencode(q) if q else "")
    return json.load(urllib.request.urlopen(url, timeout=120))

def fb_range(start_ms, end_ms):
    return get("readings", orderBy='"$key"', startAt=f'"{start_ms}"', endAt=f'"{end_ms}"') or {}

before = sorted(int(k) for k in fb_range(1789000000000, 1789800000000))
last_before = before[-1]
first_after = min(int(k) for k in fb_range(1792600000000, 1792800000000))
lo, hi = last_before / 1000, first_after / 1000
rows = [r for r in rows if lo < r["t"] < hi]
overlaps = sum(1 for a, b in zip(rows, rows[1:]) if b["t"] - a["t"] < 60)
assert overlaps == 0, f"{overlaps} lectures à moins d'une minute l'une de l'autre — recalage à revoir"

# ─────────────────────────────── 3. pluie du jour (jour local réel) ─────────────────────────
acc, day = 0.0, None
for r in rows:
    d = D.datetime.fromtimestamp(r["t"], EDT).date()
    if d != day:
        acc, day = 0.0, d
    acc += r.pop("rain_inc_mm")
    r["rday"] = round(acc, 1)

# ─────────────────── 4. sondes du lac (téléphone) jointes à la lecture GW la plus proche (±150 s)
esp = [json.loads(l) for l in open(f"{HERE}\\esp32.jsonl", encoding="utf-8") if l.strip()]
esp = [(D.datetime.fromisoformat(e["ts"]).timestamp(), e) for e in esp if e.get("src") == "esp32"]
esp = [(t, e) for t, e in esp if lo < t < hi]
ts = [r["t"] for r in rows]
matched = 0
for t, e in esp:
    i = bisect.bisect_left(ts, t)
    cands = [j for j in (i - 1, i) if 0 <= j < len(rows) and abs(rows[j]["t"] - t) <= 150]
    if cands:
        j = min(cands, key=lambda j: abs(rows[j]["t"] - t))
        rows[j].update(air=e["air"], surface=e["surface"], depth=e["depth"])
        matched += 1

FIELDS = ["air", "airb", "depth", "gust", "humb", "press", "rday", "rrate", "solar", "surface", "uv", "wdir", "wind"]
readings = {str(int(r["t"] * 1000)): {k: r[k] for k in FIELDS if r.get(k) is not None} for r in rows}

# ─────────────────────────────── 5. /daily ──────────────────────────────────────────────────
# Même formule que script.manitou_aggregate_daily de HA (clé = minuit UTC), sauf : une moyenne
# n'est écrite que si au moins MIN_N lectures portent la valeur (évite qu'une demi-journée de
# sondes du lac passe pour la moyenne du jour). Sinon null.
MIN_N = 144  # 50 % d'une journée à 5 min
DAY_FIRST = 1789689600000   # 2026-09-18 00:00 UTC (déjà présent dans /daily, calculé sur une demi-journée)
DAY_LAST = 1792540800000    # 2026-10-21 00:00 UTC (le 22 oct. n'est pas fini -> laissé à HA)

def mean(vals, dec):
    return round(sum(vals) / len(vals), dec) if len(vals) >= MIN_N else None

def aggregate(day):
    v = list(day.values())
    col = lambda k, skip0=False: [float(x[k]) for x in v if x.get(k) is not None and not (skip0 and x[k] == 0)]
    wd = col("wdir")
    u = sum(math.sin(math.radians(d)) for d in wd); c = sum(math.cos(math.radians(d)) for d in wd)
    r = math.hypot(u, c) / len(wd) if wd else 0
    return {
        "air": mean(col("air"), 2), "surface": mean(col("surface"), 2), "depth": mean(col("depth"), 2),
        # véranda : les 0.0 sont des capteurs débranchés (float(0) dans HA), pas des mesures
        "airv": mean(col("airv", True), 2), "hum": mean(col("hum", True), 2),
        "airb": mean(col("airb"), 2), "humb": mean(col("humb"), 2),
        "wind": mean(col("wind"), 1),
        "gustmax": round(max(col("gust")), 1) if col("gust") else None,
        "wdirdom": int(round((math.degrees(math.atan2(u, c)) + 360) % 360)) if wd and r >= 0.2 else None,
        "rday": round(max(col("rday")), 1) if col("rday") else None,
        "uv": mean(col("uv"), 1), "solar": mean(col("solar"), 0), "press": mean(col("press"), 1),
        "n": len(v),
    }

existing_daily = get("daily", shallow="true") or {}
pre = fb_range(DAY_FIRST, last_before)  # matin du 18 sept. déjà dans Firebase
merged = {**pre, **readings}
daily = {}
for dk in range(DAY_FIRST, DAY_LAST + 1, 86400000):
    day = {k: x for k, x in merged.items() if dk <= int(k) < dk + 86400000}
    if day:
        daily[str(dk)] = aggregate(day)

# ─────────────────────────────── 6. aperçu ──────────────────────────────────────────────────
json.dump({"readings": readings, "daily": daily}, open(f"{HERE}\\backfill_preview.json", "w"), indent=0)
fmt = lambda t: D.datetime.fromtimestamp(t, EDT).strftime("%Y-%m-%d %H:%M")
print(f"Fenêtre : {fmt(lo)} -> {fmt(hi)} (heure de l'Est)")
print(f"/readings : {len(readings)} lectures à ajouter (attendu ~{int((hi - lo) / 300)})"
      f" | sondes du lac jointes {matched}/{len(esp)}")
print(f"/daily : {len(daily)} jours (UTC) du {fmt(DAY_FIRST / 1000 + 14400)[:10]} au {fmt(DAY_LAST / 1000 + 14400)[:10]}"
      f" | déjà présents (seront remplacés) : {[fmt(int(k) / 1000 + 14400)[:10] for k in daily if k in existing_daily]}")
print("\n jour        n   lac:surf  4pi   air | airb  humb  press   vent rafale dir pluie  uv  solaire")
s = lambda x, w=5: f"{x:>{w}}" if x is not None else f"{'—':>{w}}"
for k, a in daily.items():
    print(f" {fmt(int(k) / 1000 + 14400)[:10]} {a['n']:4d}  {s(a['surface'])} {s(a['depth'])} {s(a['air'])} |"
          f" {s(a['airb'])} {s(a['humb'])} {s(a['press'], 6)} {s(a['wind'])} {s(a['gustmax'])} {s(a['wdirdom'], 4)}"
          f" {s(a['rday'])} {s(a['uv'], 4)} {s(a['solar'], 5)}")

if not WRITE:
    print("\nAPERÇU seulement — rien n'a été écrit. Pour écrire : python backfill.py --ecrire")
    sys.exit(0)

# ─────────────────────────────── 7. écriture ────────────────────────────────────────────────
inside = fb_range(int(lo * 1000) + 1, int(hi * 1000) - 1)
assert not inside, f"{len(inside)} lectures déjà présentes dans la fenêtre — arrêt (rien écrit)"
token = None
for essai in range(3):
    pwd = getpass.getpass(f"\nMot de passe Firebase de {WRITER} (non affiché) : ").strip()
    req = urllib.request.Request(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}",
        data=json.dumps({"email": WRITER, "password": pwd, "returnSecureToken": True}).encode(),
        headers={"Content-Type": "application/json"})
    try:
        token = json.load(urllib.request.urlopen(req, timeout=30))["idToken"]
        print("  Connexion Firebase OK")
        break
    except urllib.error.HTTPError as e:
        msg = json.load(e).get("error", {}).get("message", "?")
        print(f"  Connexion refusée par Firebase : {msg} ({len(pwd)} caractères saisis)")
    finally:
        del pwd
if not token:
    sys.exit("Abandon — rien n'a été écrit.")

def patch(path, body):
    r = urllib.request.Request(f"{RTDB}/{path}.json?auth={token}", data=json.dumps(body).encode(), method="PATCH",
                               headers={"Content-Type": "application/json"})
    urllib.request.urlopen(r, timeout=120).read()

keys = sorted(readings)
for i in range(0, len(keys), 500):
    patch("readings", {k: readings[k] for k in keys[i:i + 500]})
    print(f"  /readings {min(i + 500, len(keys))}/{len(keys)}")
patch("daily", {k: {f: v for f, v in a.items() if v is not None} for k, a in daily.items()})
print(f"  /daily {len(daily)} jours écrits")

# faux 0.0 de la véranda depuis le retour du lien -> champs retirés (null = suppression dans RTDB)
since = fb_range(first_after, 9999999999999)
zeros = {f"{k}/{f}": None for k, x in since.items() for f in ("airv", "hum") if x.get(f) == 0}
if zeros:
    patch("readings", zeros)
print(f"  véranda : {len(zeros)} faux 0.0 retirés")

check = fb_range(int(lo * 1000) + 1, int(hi * 1000) - 1)
print(f"\nVérification : {len(check)}/{len(readings)} lectures présentes dans la fenêtre. Terminé.")
