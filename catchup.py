"""
Catch-up one-shot : envoie tout l'historique HA vers Google Sheets.
Lancer une seule fois depuis n'importe quel PC sur le même réseau que HA.
"""

import requests
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# ── CONFIG ────────────────────────────────────────────────────────────────────
HA_URL   = "http://192.168.11.3:8123/"   # ou http://IP_DU_PI:8123
HA_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiIyNGI0YjIzYzU2ODA0NjcxYmRkMGI0MmQ1YmNlMTQxOSIsImlhdCI6MTc4Mjc1NTgxNywiZXhwIjoyMDk4MTE1ODE3fQ.v9azlyLpVyyWIIQ94Z7k7O7XdikKmVVy3g9eemdK2oo"            # voir instructions ci-dessous

GAS_URL  = "https://script.google.com/macros/s/AKfycbwF_3eis5gtHZnV1znEYmQDjTM8DcxDqSR4YngAATKqLr2a1dtEfcWpC1ydgnXyG8g/exec"

ENTITIES = {
    "air":     "sensor.sondes_quai_lac_manitou_temperature_air",
    "surface": "sensor.sondes_quai_lac_manitou_temperature_surface",
    "depth":   "sensor.sondes_quai_lac_manitou_temperature_4_pi",
}

DAYS_BACK = 10   # HA garde ~10 jours par défaut
# ─────────────────────────────────────────────────────────────────────────────

def fetch_history(entity_id, start, end):
    headers = {"Authorization": f"Bearer {HA_TOKEN}"}
    from urllib.parse import urlencode
    base = HA_URL.rstrip("/")
    start_str = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str   = end.strftime("%Y-%m-%dT%H:%M:%SZ")
    params = urlencode({"filter_entity_id": entity_id, "end_time": end_str, "minimal_response": "true"})
    url = f"{base}/api/history/period/{start_str}?{params}"
    r = requests.get(url, headers=headers, timeout=30)
    if not r.ok:
        print(f"     HTTP {r.status_code}: {r.text[:300]}")
        r.raise_for_status()
    states = r.json()
    return states[0] if states else []

def main():
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=DAYS_BACK)

    print(f"Récupération de l'historique du {start:%Y-%m-%d} au {end:%Y-%m-%d}...")

    # Récupérer l'historique de chaque capteur
    histories = {}
    for key, entity_id in ENTITIES.items():
        print(f"  -> {entity_id}")
        histories[key] = fetch_history(entity_id, start, end)
        print(f"     {len(histories[key])} états trouvés")

    # Aligner les données par timestamp (grouper par minute)
    buckets = defaultdict(dict)
    for key, states in histories.items():
        for state in states:
            try:
                val = float(state["state"])
                # Conserver le timestamp UTC complet, tronquer à la minute pour aligner les 3 capteurs
                ts_raw = state["last_changed"]  # ex: "2026-06-29T18:30:45.123456+00:00"
                ts_dt  = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                ts_key = ts_dt.strftime("%Y-%m-%dT%H:%MZ")  # clé UTC sans ambiguïté
                buckets[ts_key]["_dt"]  = ts_dt
                buckets[ts_key][key]    = val
            except (ValueError, KeyError):
                pass  # ignorer les états 'unknown' / 'unavailable'

    # Ne garder que les timestamps avec les 3 capteurs disponibles
    complete = [
        {
            "timestamp": vals["_dt"].strftime("%Y-%m-%dT%H:%M:%S+00:00"),  # UTC explicite
            "air":       vals["air"],
            "surface":   vals["surface"],
            "depth":     vals["depth"],
        }
        for ts, vals in sorted(buckets.items())
        if all(k in vals for k in ("air", "surface", "depth", "_dt"))
    ]

    print(f"\n{len(complete)} points complets à envoyer.")

    if not complete:
        print("Rien à envoyer.")
        return

    # Envoyer en chunks de 500 pour éviter les timeouts
    CHUNK = 500
    for i in range(0, len(complete), CHUNK):
        chunk = complete[i:i+CHUNK]
        print(f"  Envoi chunk {i//CHUNK + 1} ({len(chunk)} lignes)...", end=" ", flush=True)
        r = requests.post(GAS_URL, json=chunk, timeout=60, allow_redirects=True)
        try:
            result = r.json()
            print(f"OK - {result} (status={r.status_code})")
        except Exception:
            print(f"Reponse brute: {r.status_code} {r.text[:200]}")

    print("\nCatch-up termine!")

if __name__ == "__main__":
    main()
