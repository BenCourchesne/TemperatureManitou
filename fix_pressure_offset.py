#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Correction rétroactive de la pression : les lectures historiques ont été
enregistrées avec « Altitude for REL = 0 » sur la passerelle GW3000, donc la
« pression relative » loggée était en réalité la pression ABSOLUE (~964 hPa au
lieu de ~1011 hPa au niveau de la mer, station à ~390 m).

Une fois l'altitude corrigée sur la passerelle (1280 ft), les données FUTURES
sont bonnes. Ce script rajoute le même offset constant aux données PASSÉES
(/readings et /daily) pour que l'historique soit continu avec le futur.

OFFSET (hPa) = REL_nouveau − ABS  lu sur la console juste après avoir enregistré
l'altitude. C'est la valeur autoritaire (la passerelle applique un offset
constant fonction de l'altitude). Valeur calculée pour 390 m ≈ +46 hPa, mais
UTILISE CELLE DE LA CONSOLE si tu peux la lire.

Idempotent : ne corrige que les enregistrements dont press < THRESHOLD. Les
valeurs déjà corrigées (~1011) sont au-dessus du seuil, donc une relance ne
double pas l'offset. Les enregistrements sans champ press (avant l'ajout du
capteur) sont ignorés.

Usage :
    python fix_pressure_offset.py --offset 47              # DRY RUN
    python fix_pressure_offset.py --offset 47 --write      # applique
"""

import sys

import requests

from backfill_veranda import FB, fb_signin, fb_readings

# Console Windows (cp1252) : force l'UTF-8 pour les accents / caractères de tracé.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

# Séparateur pré-correction (≤ ~971) / post-correction (~1010). Marge ~20 hPa
# de chaque côté : sûr et idempotent.
THRESHOLD = 990.0


def parse_args():
    write = "--write" in sys.argv
    offset = None
    if "--offset" in sys.argv:
        offset = float(sys.argv[sys.argv.index("--offset") + 1])
    return offset, write


def fb_daily():
    r = requests.get(f"{FB}/daily.json", timeout=120)
    r.raise_for_status()
    return r.json() or {}


def main():
    offset, write = parse_args()
    if offset is None:
        print("ERREUR : précise --offset <hPa> (REL−ABS lu sur la console).")
        sys.exit(1)

    mode = "ÉCRITURE" if write else "DRY RUN (lecture seule)"
    print(f"Mode : {mode}  |  offset = +{offset:g} hPa  |  seuil = {THRESHOLD:g} hPa\n")

    token = fb_signin() if write else None

    # dec = décimales à conserver (readings = entier, daily = 1 décimale)
    for node, data, dec in (("readings", fb_readings(), 0),
                            ("daily",    fb_daily(),    1)):
        keys = sorted(data.keys(), key=int)
        todo, skip_nop, skip_done, failed = [], 0, 0, 0
        for k in keys:
            rec = data[k]
            if not isinstance(rec, dict) or rec.get("press") is None:
                skip_nop += 1
                continue
            old = float(rec["press"])
            if old >= THRESHOLD:          # déjà corrigé (ou déjà au niveau mer)
                skip_done += 1
                continue
            new = round(old + offset, dec) if dec > 0 else int(round(old + offset))
            todo.append((k, old, new))

        print(f"── /{node} : {len(todo)} à corriger, "
              f"{skip_done} déjà OK, {skip_nop} sans press")
        if todo:
            k0, o0, n0 = todo[0]
            k1, o1, n1 = todo[-1]
            print(f"   ex. {k0}: {o0} → {n0}   …   {k1}: {o1} → {n1}")

        if not write:
            continue
        for k, _old, new in todo:
            rr = requests.patch(f"{FB}/{node}/{k}.json?auth={token}",
                                json={"press": new}, timeout=30)
            if rr.status_code != 200:
                failed += 1
                if failed <= 5:
                    print(f"   échec {k} : {rr.status_code} {rr.text[:80]}")
        print(f"   → {len(todo) - failed} écrits, {failed} échecs")

    if not write:
        print("\n→ DRY RUN. Vérifie l'offset et les exemples, puis relance "
              "avec --write pour appliquer.")


if __name__ == "__main__":
    main()
