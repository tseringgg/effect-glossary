#!/usr/bin/env sh
# Word-overlap similarity over the deduped full-corpus glossary: validation
# report, then the first-pass HDBSCAN clustering (raw overlap only), then the
# side-by-side comparison page (reads data/full/clusters.json for its cluster
# panel, so clustering must run first), then the check that the page's matrix
# ranking matches brute force. Needs data/full/effects.json, so run
# run_zone_corpus.sh first if it is not there.
set -e
cd "$(dirname "$0")/src"
python validate_similarity.py
python cluster_effects.py
python build_similarity_page.py
python check_page_agreement.py
