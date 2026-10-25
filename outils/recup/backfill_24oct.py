"""Rattrapage du 24 oct. 2026 : radio côté maison coupée (disjoncteur, remplacement de ventilateurs).

Le quai est resté alimenté : la GW3000 a continué d'écrire sur sa SD (horloge NTP, bien datée),
l'ESP32 tournait mais personne ne recueillait ses mesures (téléphone collecteur retiré).

  Météo        : gw3000/202610A (2).csv, re-téléchargé le 2026-10-25.
  Surface/4 pi : interpolation linéaire entre les lectures qui bordent chaque trou.
  Air ESP32    : air GW3000 + écart (ESP32 - GW3000) interpolé entre les bords du trou.
  Ces lectures portent est: 1 (pointillés sur le site pour surface/4 pi).

  python backfill_24oct.py            -> aperçu, n'écrit rien
  python backfill_24oct.py --ecrire   -> demande le mot de passe ha-writer, écrit /readings
                                         puis recalcule /daily du 2026-10-24 (UTC)
"""
import csv, json, math, sys, getpass, datetime as D, urllib.request, urllib.parse, urllib.error

HERE = r"D:\Claude desktop\ESPHome\recup"
SD_FILE = "202610A (2).csv"
RTDB = "https://lac-manitou-temperatures-d284a-default-rtdb.firebaseio.com"
API_KEY = "AIzaSyANzIvc-kAmlLyn7wxdpyPSsRFNNmwXulY"
WRITER = "ha-writer@manitou.local"
EDT = D.timezone(D.timedelta(hours=-4))
DAY24 = 1792800000000  # 2026-10-24 00:00 UTC
DAY_MS = 86400000

def get(path, **q):
    url = f"{RTDB}/{path}.json" + ("?" + urllib.parse.urlencode(q) if q else "")
    return json.load(urllib.request.urlopen(url, timeout=120)) or {}

def fb_range(a, b):
    return get("readings", orderBy='"$key"', startAt=f'"{a}"', endAt=f'"{b}"')

fmt = lambda ms: D.datetime.fromtimestamp(ms / 1000, EDT).strftime("%m-%d %H:%M")

# trous > 7 min dans la journée UTC du 24 (bornes incluses : dernière lecture du 23, première du 25)
fb = fb_range(DAY24 - 3600000, DAY24 + DAY_MS + 3600000)
keys = sorted(int(k) for k in fb)
gaps = [(a, b) for a, b in zip(keys, keys[1:]) if b - a > 7 * 60000 and DAY24 <= b and a < DAY24 + DAY_MS]

num = lambda v: v not in ("--", "", None)
sd = []
for r in csv.DictReader(open(f"{HERE}\\gw3000\\{SD_FILE}", encoding="utf-8-sig")):
    g = lambda col, fn: fn(r[col]) if num(r[col]) else None
    sd.append((int(r["Timestamp"]) * 1000, {k: v for k, v in {
        "airb": g("Outdoor Temperature(°F)", lambda v: round((float(v) - 32) / 1.8, 1)),
        "humb": g("Outdoor Humidity(%)", int),
        "press": g("REL Pressure(inHg)", lambda v: round(float(v) * 33.8639, 1)),
        "wind": g("Wind(mph)", lambda v: round(float(v) * 1.609344, 1)),
        "gust": g("Gust(mph)", lambda v: round(float(v) * 1.609344, 1)),
        "wdir": g("Wind Direction(deg)", int),
        "solar": g("Solar Rad(W/m2)", lambda v: round(float(v))),
        "uv": g("UV-Index", lambda v: int(float(v))),
        "rrate": g("Rain Rate(in/Hr)", lambda v: round(float(v) * 25.4, 1)),
        "rday": g("Daily Rain(in)", lambda v: round(float(v) * 25.4, 1)),
    }.items() if v is not None}))

readings = {}
for lo, hi in gaps:
    A, B = fb[str(lo)], fb[str(hi)]
    assert all(k in A and k in B for k in ("surface", "depth", "air", "airb")), f"bord incomplet {fmt(lo)}/{fmt(hi)}"
    offA, offB = A["air"] - A["airb"], B["air"] - B["airb"]
    rows = [(t, w) for t, w in sd if lo < t < hi]
    for t, w in rows:
        f = (t - lo) / (hi - lo)
        lerp = lambda a, b: a + (b - a) * f
        x = dict(w, surface=round(lerp(A["surface"], B["surface"]), 2), depth=round(lerp(A["depth"], B["depth"]), 2), est=1)
        if "airb" in w:
            x["air"] = round(w["airb"] + lerp(offA, offB), 2)
        readings[str(t)] = x
    print(f"Trou {fmt(lo)} -> {fmt(hi)} ({(hi - lo) / 60000:.0f} min) : {len(rows)} lignes SD"
          f" | surface {A['surface']}->{B['surface']}  4pi {A['depth']}->{B['depth']}"
          f"  écart air ESP32-GW3000 {offA:+.2f}->{offB:+.2f}")
assert readings, "aucune ligne SD dans les trous : le bon fichier est-il dans gw3000\\ ?"

big = max(gaps, key=lambda g: g[1] - g[0])
print("\nExtrait du grand trou (heure locale) :")
for k in sorted(int(k) for k in readings if big[0] < int(k) < big[1])[::6]:
    x = readings[str(k)]
    print(f"  {fmt(k)}  air {x.get('air')}  airb {x.get('airb')}  surf {x['surface']}  4pi {x['depth']}"
          f"  solar {x.get('solar')}  vent {x.get('wind')}  press {x.get('press')}")

# /daily du 24 oct. (UTC) recalculé : formule HA (scripts.yaml)
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

in_day = lambda k: DAY24 <= int(k) < DAY24 + DAY_MS
day24 = {**{k: v for k, v in fb.items() if in_day(k)}, **{k: v for k, v in readings.items() if in_day(k)}}
new24 = aggregate(day24)
old24 = get(f"daily/{DAY24}")
print(f"\n/daily 2026-10-24 actuel : {old24}")
print(f"/daily 2026-10-24 nouveau: {new24}")

if "--ecrire" not in sys.argv:
    print(f"\nAPERÇU seulement — rien n'a été écrit ({len(readings)} lectures prêtes)."
          " Pour écrire : python backfill_24oct.py --ecrire")
    sys.exit(0)

assert not any(fb_range(lo + 1, hi - 1) for lo, hi in gaps), "des lectures sont déjà présentes dans un trou — arrêt"
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
send("PUT", f"daily/{DAY24}", new24)
print("  /daily 2026-10-24 recalculé")
present = sum(len(fb_range(lo + 1, hi - 1)) for lo, hi in gaps)
print(f"\nVérification : {present}/{len(readings)} lectures présentes dans les trous. Terminé.")
