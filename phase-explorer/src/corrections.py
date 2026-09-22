"""Load and apply the hand-maintained corrections overlay.

corrections/corrections.json documents known-wrong phase.rs parses, found
during real use of this tool, never during automated coverage sweeps. It is
applied on top of data/card-data.json at our own build time -- their file is
never touched, their engine is never run to validate a fix.

Two correction kinds:
  flag  -- the raw structure ships unchanged; the correction record is
           attached for display so the defect is visible next to the card.
  patch -- a value substitution is applied to a deep copy before indexing,
           used only when corrections.json's `patch` list is non-null.

See corrections/SCHEMA.md for the entry format and the reasoning for why
`flag` is the default.
"""
import copy
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(HERE, "corrections", "corrections.json")


def load(path=PATH):
    """oracle_id -> list of correction entries (usually one, but not assumed)."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        entries = json.load(fh)
    by_oid = {}
    for e in entries:
        by_oid.setdefault(e["oracle_id"], []).append(e)
    return by_oid


def _set_path(obj, dotted, value):
    parts = dotted.split(".")
    for p in parts[:-1]:
        obj = obj[p]
    obj[parts[-1]] = value


def apply(entry, oracle_id, corrections_by_oid):
    """Return (possibly-patched deep copy of entry, list of applicable corrections).

    The list is returned even for flag-only corrections (patch is a no-op on
    the data but the record still needs to reach the index/chunk output).
    Entries with no matching oracle_id pass through untouched, sharing the
    original object rather than copying, since the common case is "no
    correction applies" and 34,645 unnecessary deep copies would be wasteful.
    """
    matches = corrections_by_oid.get(oracle_id)
    if not matches:
        return entry, []
    patched = copy.deepcopy(entry)
    for c in matches:
        if c.get("kind") == "patch" and c.get("patch"):
            for op in c["patch"]:
                _set_path(patched, op["path"], op["value"])
    return patched, matches
