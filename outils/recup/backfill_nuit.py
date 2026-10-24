"""Rattrapage de la nuit du 22 au 23 oct. 2026 (Pi débranché) + nettoyage /daily du 22 oct.

Source : gw3000/202610A.csv re-téléchargé APRÈS le retour (horloge NTP, bien daté).
Sondes du lac : aucune (ESP32 hors réseau pendant le trou).

  python backfill_nuit.py            -> aperçu, n'écrit rien
  python backfill_nuit.py --ecrire   -> demande le mot de passe ha-writer, écrit /readings
                                        puis recalcule /daily du 2026-10-22 (UTC) sans les faux 0.0
"""
import csv, json, math, sys, getpass, datetime as D, urllib.request, urllib.parse, urllib.error

HERE = r"D:\Claude desktop\ESPHome\recup"
RTDB = "https://lac-manitou-temperatures-d284a-default-rtdb.firebaseio.com"
API_KEY = "AIzaSyANzIvc-kAmlLyn7wxdpyPSsRFNNmwXulY"
WRITER = "ha-writer@manitou.local"
EDT = D.timezone(D.timedelta(hours=-4))
DAY22 = 1792627200000  # 2026-10-22 00:00 UTC

def get(path, **q):
    url = f"{RTDB}/{path}.json" + ("?" + urllib.parse.urlencode(q) if q else "")
    return json.load(urllib.request.urlopen(url, timeout=120)) or {}

def fb_range(a, b):
    return get("readings", orderBy='"$key"', startAt=f'"{a}"', endAt=f'"{b}"')

# fenêtre = trou réel dans Firebase autour de la nuit
around = sorted(int(k) for k in fb_range(1792700000000, 1792800000000))
gaps = [(a, b) for a, b in zip(around, around[1:]) if b - a > 30 * 60000]
assert len(gaps) == 1, f"trou attendu unique, trouvé {gaps}"
lo, hi = gaps[0]

num = lambda v: v not in ("--", "", None)
rows = []
for r in csv.DictReader(open(f"{HERE}\\gw3000\\202610A.csv", encoding="utf-8-sig")):
    t = int(r["Timestamp"])
    if not (lo / 1000 < t < hi / 1000): continue
    g = lambda col, fn: fn(r[col]) if num(r[col]) else None
    rows.append((t, {k: v for k, v in {
        "airb": g("Outdoor Temperature(°F)", lambda v: round((float(v) - 32) / 1.8, 1)),
        "humb": g("Outdoor Humidity(%)", int),
        "press": g("REL Pressure(inHg)", lambda v: round(float(v) * 33.8639, 1)),
        "wind": g("Wind(mph)", lambda v: round(float(v) * 1.609344, 1)),
        "gust": g("Gust(mph)", lambda v: round(float(v) * 1.609344, 1)),
        "wdir": g("Wind Direction(deg)", int),
        "solar": g("Solar Rad(W/m2)", lambda v: round(float(v))),
        "uv": g("UV-Index", lambda v: int(float(v))),
        "rrate": g("Rain Rate(in/Hr)", lambda v: round(float(v) * 25.4, 1)),
        "rday": g("Daily Rain(in)", lambda v: round(float(v) * 25.4, 1)),  # horloge valide -> compteur du jour fiable
    }.items() if v is not None}))
readings = {str(t * 1000): v for t, v in rows}
fmt = lambda ms: D.datetime.fromtimestamp(ms / 1000, EDT).strftime("%m-%d %H:%M")
print(f"Trou Firebase : {fmt(lo)} -> {fmt(hi)}")
print(f"Lectures GW3000 dans le trou : {len(readings)} (attendu ~{(hi - lo) // 300000})")
assert readings, "aucune lecture : le fichier 202610A.csv a-t-il été re-téléchargé après le retour ?"
ks = sorted(int(k) for k in readings)
print(f"   de {fmt(ks[0])} à {fmt(ks[-1])} | ex. {readings[str(ks[0])]}")

# /daily du 22 oct. (UTC) recalculé : formule HA, en ignorant les 0.0 de la véranda
def aggregate(day):
    v = list(day.values())
    col = lambda k, skip0=False: [float(x[k]) for x in v if x.get(k) is not None and not (skip0 and x[k] == 0)]
    m = lambda xs, d: round(sum(xs) / len(xs), d) if xs else None
    wd = col("wdir")
    u = sum(math.sin(math.radians(x)) for x in wd); c = sum(math.cos(math.radians(x)) for x in wd)
    r = math.hypot(u, c) / len(wd) if wd else 0
    out = {"air": m(col("air"), 2), "surface": m(col("surface"), 2), "depth": m(col("depth"), 2),
           "airv": m(col("airv", True), 2), "hum": m(col("hum", True), 2),
           "airb": m(col("airb"), 2), "humb": m(col("humb"), 2), "wind": m(col("wind"), 1),
           "gustmax": round(max(col("gust")), 1) if col("gust") else None,
           "wdirdom": int(round((math.degrees(math.atan2(u, c)) + 360) % 360)) if wd and r >= 0.2 else None,
           "rday": round(max(col("rday")), 1) if col("rday") else None,
           "uv": m(col("uv"), 1), "solar": m(col("solar"), 0), "press": m(col("press"), 1), "n": len(v)}
    return {k: x for k, x in out.items() if x is not None}

day22 = {**fb_range(DAY22, DAY22 + 86399999), **{k: v for k, v in readings.items() if DAY22 <= int(k) < DAY22 + 86400000}}
new22 = aggregate(day22)
old22 = get(f"daily/{DAY22}")
print(f"\n/daily 2026-10-22 actuel : {old22}")
print(f"/daily 2026-10-22 nouveau: {new22}")

if "--ecrire" not in sys.argv:
    print("\nAPERÇU seulement — rien n'a été écrit. Pour écrire : python backfill_nuit.py --ecrire")
    sys.exit(0)

assert not fb_range(lo + 1, hi - 1), "des lectures sont déjà présentes dans le trou — arrêt"
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

def send(method, path, body):
    r = urllib.request.Request(f"{RTDB}/{path}.json?auth={token}", data=json.dumps(body).encode(), method=method,
                               headers={"Content-Type": "application/json"})
    urllib.request.urlopen(r, timeout=120).read()

send("PATCH", "readings", readings)
print(f"  /readings : {len(readings)} lectures écrites")
send("PUT", f"daily/{DAY22}", new22)
print("  /daily 2026-10-22 recalculé")
zeros = {f"{k}/{f}": None for k, x in fb_range(DAY22, DAY22 + 2 * 86400000).items()
         for f in ("airv", "hum") if x.get(f) == 0}
if zeros:
    send("PATCH", "readings", zeros)
print(f"  véranda : {len(zeros)} faux 0.0 retirés de /readings")
print(f"\nVérification : {len(fb_range(lo + 1, hi - 1))}/{len(readings)} lectures présentes dans le trou. Terminé.")
