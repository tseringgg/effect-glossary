#!/usr/bin/env python3
"""The group-search log: what was typed in the main search box, how many results it had, and whether a result was opened. Written by src/serve.py (POST /api/groupsearch/log), read by nobody but you.

One file, build/group_search_log.json (build/ is gitignored, so it is never committed), keyed by the folded query so it stays small:
    {"v": 1, "queries": {"board wipe": {"q": "board wipe", "searches": 4, "zero": 0, "groups": 6, "cards": 3, "opened": 2, "first": "...", "last": "..."}}}
`zero` counts the searches that had no group and no card. Only the folded words are stored: no card, no identity, no address.
Size-limited and rotated: at 2,000 distinct queries or 400 KB the file is moved to group_search_log.1.json (replacing the previous one) and a new one starts. Every write goes to a temp file in the same folder, is flushed
and fsynced, then renamed over the file; a corrupt file is refused and never overwritten. The endpoint answers 404 when the group search is off (build/group_search/meta.json is absent).
"""
import datetime
import io
import json
import os
import re
import tempfile
import threading

import manual_common as M

LOG = os.environ.get("GROUP_SEARCH_LOG") or os.path.join(M.HERE, "build", "group_search_log.json")                 # the env override is for the tests only
META = os.environ.get("GROUP_SEARCH_META") or os.path.join(M.HERE, "build", "group_search", "meta.json")
MAX_BODY = 512
MAX_QUERIES = 2000
MAX_BYTES = 400 * 1024
MAX_Q = 60
FIELDS = {"q", "t", "groups", "cards"}
_lock = threading.Lock()


def enabled():
    return os.path.exists(META)


def fold(s):
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"['’]", "", s.lower())).strip()


def validate(body):
    """-> (folded query, kind, groups, cards). Raises M.ApiError."""
    if not isinstance(body, dict):
        raise M.ApiError(400, "body must be a JSON object")
    extra = set(body) - FIELDS
    if extra:
        raise M.ApiError(400, "unknown field(s): " + ", ".join(sorted(extra)))
    q, kind = body.get("q"), body.get("t")
    if not isinstance(q, str) or len(q) > 200:
        raise M.ApiError(400, "q must be text")
    q = fold(q)[:MAX_Q].strip()
    if len(q) < 2:
        raise M.ApiError(422, "q is empty after folding")
    if kind not in ("search", "open"):
        raise M.ApiError(400, "t must be search or open")
    g, c = body.get("groups", 0), body.get("cards", 0)
    for v in (g, c):
        if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 100000:
            raise M.ApiError(400, "groups and cards must be whole numbers from 0 to 100000")
    return q, kind, g, c


def load(path=None):
    path = path or LOG
    if not os.path.exists(path):
        return {"v": 1, "queries": {}}
    with io.open(path, encoding="utf-8") as fh:
        try:
            d = json.load(fh)
        except ValueError as exc:
            raise M.ApiError(500, "the log file is corrupt and was left alone: %s" % exc)
    if not isinstance(d, dict) or not isinstance(d.get("queries"), dict):
        raise M.ApiError(500, "the log file has an unexpected shape and was left alone")
    return d


def write_atomic(path, doc):
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".gslog_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=0))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def record(body, now=None, path=None):
    """Validate and apply one event; returns {"ok": True, "queries": n}. The 404 for 'search off' is the caller's (serve.py) first check."""
    q, kind, g, c = validate(body)
    path = path or LOG
    now = (now or datetime.datetime.now()).strftime("%Y-%m-%dT%H:%M:%S")
    with _lock:
        doc = load(path)
        qs = doc["queries"]
        r = qs.get(q)
        if r is None:
            r = qs[q] = {"q": q, "searches": 0, "zero": 0, "groups": 0, "cards": 0, "opened": 0, "first": now, "last": now}
        if kind == "search":
            r["searches"] += 1
            r["groups"], r["cards"] = g, c
            if g == 0 and c == 0:
                r["zero"] += 1
        else:
            r["opened"] += 1
        r["last"] = now
        text_len = len(json.dumps(doc, ensure_ascii=False))
        if len(qs) > MAX_QUERIES or text_len > MAX_BYTES:
            if os.path.exists(path):
                os.replace(path, path[:-5] + ".1.json" if path.endswith(".json") else path + ".1")
            doc = {"v": 1, "queries": {q: r}}
        write_atomic(path, doc)
        return {"ok": True, "queries": len(doc["queries"])}
