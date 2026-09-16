#!/usr/bin/env sh
# Full rebuild: fetch -> extract/dedupe -> author -> report -> ablation.
set -e
cd "$(dirname "$0")/src"
python fetch_cards.py
python glossary.py
python author_plain_text.py
python classify_zones.py
python build_zone_viewer.py
python report.py
python ablation_cardname.py
python grid.py
python diagnose_e5.py
python remeasure_mana_dork.py
python build_page.py
