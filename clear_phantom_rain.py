#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nettoyage ponctuel : efface une pluie fantôme dans /readings.

Le compteur daily_rain de la WS69 portait une valeur résiduelle (rday=1.3 mm
avec rrate=0 partout — donc aucune pluie réelle) le soir du 2026-07-07 jusqu'au
reset de minuit. On remet rday=0 sur ces lectures (additif : rrate déjà 0,
et air/surface/depth/vent/etc. NE SONT PAS touchés — on ne supprime rien).

Corriger les /readings suffit : l'agrégation /daily les relit, donc pas de
re-pollution. Idempotent.

Usage :
    python clear_phantom_rain.py            # DRY RUN (lecture seule)
    python clear_phantom_rain.py --write    # applique (rday -> 0)
"""

import sys
from datetime import datetime

import requests
from backfill_veranda import FB, fb_signin, fb_readings


def main():
    write = "--write" in sys.argv
    print(f"Mode : {'ÉCRITURE' if write else 'DRY RUN (lecture seule)'}")

    readings = fb_readings()
    # Cible : rday présent et non nul (actuellement = la seule pluie fantôme).
    targets = {
        k: v for k, v in readings.items()
        if isinstance(v, dict) and v.get("rday") not in (None, 0)
    }
    if not targets:
        print("Aucune lecture avec rday non nul. Rien à faire.")
        return

    keys = sorted(targets, key=int)
    vals = sorted({targets[k].get("rday") for k in keys})
    t0 = datetime.fromtimestamp(int(keys[0]) / 1000)
    t1 = datetime.fromtimestamp(int(keys[-1]) / 1000)
    print(f"{len(keys)} lectures ciblées  |  {t0}  ->  {t1}")
    print(f"Valeurs rday rencontrées : {vals}")
    # Vérif de sûreté : rrate doit être 0/absent (sinon vraie pluie → on stoppe).
    bad = [k for k in keys if targets[k].get("rrate") not in (None, 0)]
    if bad:
        print(f"⚠️ {len(bad)} lectures ont rrate != 0 (pluie réelle ?). "
              f"Ex. {bad[:3]} — ABANDON par sécurité, vérifier manuellement.")
        return

    if not write:
        print("→ DRY RUN. Relance avec  --write  pour mettre rday=0.")
        return

    token = fb_signin()
    updated = failed = 0
    for k in keys:
        rr = requests.patch(f"{FB}/readings/{k}.json?auth={token}",
                            json={"rday": 0}, timeout=30)
        if rr.status_code == 200:
            updated += 1
        else:
            failed += 1
            if failed <= 5:
                print(f"  échec {k} : {rr.status_code} {rr.text[:80]}")
    print(f"Terminé : {updated} remises à 0, {failed} échecs.")


if __name__ == "__main__":
    main()
