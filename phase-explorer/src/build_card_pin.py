#!/usr/bin/env python3
"""Card pin: a card result in the search box opens the card in its best group, pinned at the top ("You searched for this card"), instead of the card page. NEW FILE ONLY: build/card_pin/meta.json.

    python src/build_card_pin.py

CARD_PIN = True writes build/card_pin/meta.json, which is all the page looks for (one small request at load); False writes nothing and removes it, so the page keeps opening the card page and the build directory is exactly
the build without this feature. The logic is reports/cardpin.js (pure ES5); the page is reports/browse.html. Nothing is placed, no group id, leaf, threshold or figure changes, and no data is read or written here.
"""
import io
import json
import os
import shutil
import sys

CARD_PIN = True
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.environ.get("CARD_PIN_OUT") or os.path.join(HERE, "build", "card_pin")          # the env override is for the tests only
ORDER = ["precise", "tentative", "tag", "loose", "keyword", "hand"]


def main(force=None):
    on = CARD_PIN if force is None else force
    if not on:
        if os.path.isdir(OUTDIR) and not os.environ.get("CARD_PIN_OUT"):
            shutil.rmtree(OUTDIR)
        print("CARD_PIN is off: nothing written")
        return 0
    os.makedirs(OUTDIR, exist_ok=True)
    with io.open(os.path.join(OUTDIR, "meta.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"v": 1, "enabled": True, "order": ORDER}, sort_keys=True, separators=(",", ":")))
    print("card pin: build/card_pin/meta.json written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
