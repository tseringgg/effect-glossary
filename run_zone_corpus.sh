#!/usr/bin/env sh
# Full-corpus zone labelling: ingest -> extract/dedupe/classify -> review page.
# Separate from run_all.sh, which runs the 30-card search experiment.
# Pass --refresh to re-download the Scryfall bulk file; otherwise the cache is used.
set -e
cd "$(dirname "$0")/src"
python ingest_bulk.py "$@"
python build_full_glossary.py
python build_zone_review.py
