#!/usr/bin/env python3
"""Batch actions for the hand-placement tool: place from suggestions, place from the fallback list, confirm or reject a soft placement, undo a batch. One request = one batch = ALL OR NOTHING.

Used by POST /api/manual/batch (src/serve.py) and the tests. The only file written is corrections/manual_placements.json (plus a copy of it in corrections/backups/ made before the write); nothing under build/ is touched.

Request  {"id": "b-...", "kind": "place|fallback|confirm|reject", "threshold": 0.9, "note": "", "items": [{"oid", "group", "action": "add|remove", "score", "source", "override"}]}
         {"undo": "<batch id>" | "last"}
Rules    1..100 items; every card and group must exist; place: the group is one of the card's top-5 suggestions and the score is the suggestions file's; fallback: the group is in the card's fallback list; confirm / reject:
         the card holds the group as a tentative, annotation, tag or sibling placement; a card that already has any hand entry is refused unless its item says override: true; no duplicate (card, group).
         Every problem is collected; if there is one, NOTHING is written and the answer lists the rows. The same batch id with the same items is accepted again as a no-op (a retry after a lost answer).
Each entry written carries batch {id, kind, threshold, score, source}; the file also keeps batches[id] = {date, kind, threshold, count, note, undone, replaced}. Entries without `batch` are single placements.
Undo removes only entries that still carry the batch id (an entry edited singly since is left alone and reported) and restores the entries the batch had replaced.
"""
import datetime
import io
import json
import os
import re
import shutil

import manual_common as M

MAX_ITEMS = 100
MAX_BODY = 65536
MIN_THRESHOLD = 0.70
KINDS = ("place", "fallback", "confirm", "reject")
SOFT_SRC = "TAMS"
ID_RE = re.compile(r"^b-[a-z0-9][a-z0-9-]{5,40}$")
ITEM_KEYS = {"oid", "group", "action", "score", "source", "override"}
KEEP_BACKUPS = 20
_cache = {}


def _load(path):
    if not os.path.exists(path):
        return None
    m = os.path.getmtime(path)
    c = _cache.get(path)
    if not c or c[0] != m:
        with io.open(path, encoding="utf-8") as fh:
            _cache[path] = (m, json.load(fh))
    return _cache[path][1]


def load_suggestions():
    d = _load(os.path.join(M.HERE, "build", "text_sug", "queue.json")) or _load(os.path.join(M.HERE, "build", "manual_suggestions.json"))      # the merged rows when TEXT_SUGGESTIONS is on
    return d["cards"] if d else None


def load_fallback():
    d = _load(os.path.join(M.HERE, "build", "manual_fallback.json"))
    return d["cards"] if d else None


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")


def _fail(status, msg, items=None):
    raise M.ApiError(status, msg, {"items": items} if items else None)


def apply_batch(body, index=None, path=None, sugg=None, fallback=None, now=None):
    index = index or M.load_index()
    if index is None:
        raise M.ApiError(503, "build/manual_index.json is missing; run python src/build_manual_layer.py")
    if not index.get("batch"):
        raise M.ApiError(404, "batch actions are switched off in this build (BATCH_ACTIONS)")
    if not isinstance(body, dict):
        raise M.ApiError(400, "body must be a JSON object")
    path = path or M.CORR
    if "undo" in body:
        if set(body) - {"undo"}:
            raise M.ApiError(400, "an undo request carries only 'undo'")
        return _undo(body["undo"], path, now)
    extra = set(body) - {"id", "kind", "threshold", "note", "items"}
    if extra:
        raise M.ApiError(400, "unknown field(s): " + ", ".join(sorted(extra)))
    bid, kind, thr, items = body.get("id"), body.get("kind"), body.get("threshold"), body.get("items")
    if not isinstance(bid, str) or not ID_RE.match(bid):
        raise M.ApiError(400, "id must look like b-20261015-153000-ab12")
    if kind not in KINDS:
        raise M.ApiError(400, "kind must be one of " + " | ".join(KINDS))
    if kind in ("place", "fallback"):
        if not _num(thr) or not MIN_THRESHOLD <= thr <= 1.0:
            raise M.ApiError(422, "threshold must be a number from %.2f to 1.00" % MIN_THRESHOLD)
    elif thr is not None and (not _num(thr) or not 0 <= thr <= 1.0):
        raise M.ApiError(422, "threshold must be a number from 0 to 1")
    note = M._clean_note(body.get("note"))
    if not isinstance(items, list) or not items:
        raise M.ApiError(400, "items must be a non-empty list")
    if len(items) > MAX_ITEMS:
        raise M.ApiError(413, "a batch holds at most %d items; this one has %d" % (MAX_ITEMS, len(items)))
    sugg = sugg if sugg is not None else load_suggestions()
    fallback = fallback if fallback is not None else load_fallback()
    if kind == "place" and sugg is None:
        raise M.ApiError(503, "build/manual_suggestions.json is missing")
    if kind == "fallback" and fallback is None:
        raise M.ApiError(503, "build/manual_fallback.json is missing")
    with M.FileLock(path):
        try:
            doc = M.load_doc(path)
        except ValueError as exc:
            raise M.ApiError(500, str(exc) + " (not overwritten; fix or remove the file)")
        sig = [(i.get("oid"), i.get("group"), i.get("action")) for i in items if isinstance(i, dict)]
        batches = doc.setdefault("batches", {})
        if bid in batches:
            old = batches[bid]
            if old.get("kind") == kind and not old.get("undone") and old.get("sig") == [list(s) for s in sig]:
                return {"ok": True, "batch": bid, "changed": False, "count": old.get("count"), "revision": doc["revision"]}
            raise M.ApiError(409, "this batch id was already used")
        errs, seen, plan = [], set(), []
        cards, groups = index["cards"], index["groups"]
        for n, it in enumerate(items):
            def bad(status, msg):
                errs.append({"row": n, "oid": it.get("oid") if isinstance(it, dict) else None, "group": it.get("group") if isinstance(it, dict) else None, "status": status, "error": msg})
            if not isinstance(it, dict) or set(it) - ITEM_KEYS:
                errs.append({"row": n, "status": 400, "error": "an item has only oid, group, action, score, source, override"})
                continue
            oid, gid, act, ov = it.get("oid"), it.get("group"), it.get("action"), it.get("override", False)
            if not isinstance(oid, str) or not M.UUID.match(oid) or not isinstance(gid, str) or ":" not in gid:
                bad(400, "oid or group is malformed")
                continue
            if not isinstance(ov, bool) or act not in ("add", "remove"):
                bad(400, "action must be add or remove and override a boolean")
                continue
            if it.get("score") is not None and (not _num(it["score"]) or not 0 <= it["score"] <= 1):
                bad(422, "score must be a number from 0 to 1")
                continue
            if it.get("source") is not None and (not isinstance(it["source"], str) or len(it["source"]) > 40):
                bad(422, "source must be text of at most 40 characters")
                continue
            card = cards.get(oid)
            if card is None:
                bad(404, "unknown card")
                continue
            if card[1] == "o":
                bad(422, "not a card in this tool")
                continue
            gi = groups.get(gid)
            if gi is None:
                bad(422, "unknown group")
                continue
            if (oid, gid) in seen:
                bad(422, "the same card and group twice in one batch")
                continue
            seen.add((oid, gid))
            held = [x[1] for x in card[3] if x[0] == gid]
            score, source = None, None
            if kind == "place":
                row = next((s for s in (sugg.get(oid) or []) if s[0] == gid), None)
                if act != "add" or row is None:
                    bad(422, "not one of this card's top-5 suggestions")
                    continue
                if not _num(it.get("score")) or abs(it["score"] - row[1]) > 0.0005:
                    bad(422, "the score does not match the suggestion (%s)" % row[1])
                    continue
                score, source = row[1], row[2]
            elif kind == "fallback":
                row = next((s for s in (fallback.get(oid) or []) if s[0] == gid), None)
                if act != "add" or row is None:
                    bad(422, "not in this card's fallback list")
                    continue
                score, source = None, "fallback:" + row[1]
            else:
                want = "add" if kind == "confirm" else "remove"
                if act != want:
                    bad(422, "%s uses action %s" % (kind, want))
                    continue
                if not any(h in SOFT_SRC for h in held):
                    bad(422, "the card does not hold this group as a tentative, annotation, tag or sibling placement")
                    continue
                score, source = it.get("score"), (it.get("source") or None)
            if act == "add":
                if any(h in M.PRECISE for h in held):
                    bad(409, "the card is already in this group (precise)")
                    continue
                if gi[4] != 1:
                    bad(422, "this group is not offered for hand placement")
                    continue
            ex = doc["edits"].get(oid)
            if ex and not ov:
                bad(409, "the card already has a hand entry; tick override to include it")
                continue
            plan.append((oid, gid, act, score, source))
        if errs:
            _fail(409 if any(e["status"] == 409 for e in errs) else 422, "batch rejected, nothing written: %d of %d item(s) refused" % (len(errs), len(items)), errs)
        date = now or datetime.datetime.now().isoformat(timespec="seconds")
        replaced, edits = {}, doc["edits"]
        for oid, gid, act, score, source in plan:
            card = cards[oid]
            e = edits.setdefault(oid, {"name": card[0], "groups": {}})
            g = e["groups"]
            for k in ([gid] + ([M.NOFIT] if act == "add" else [])):
                if k in g:
                    replaced.setdefault(oid, {"name": e["name"], "groups": {}})["groups"][k] = g[k]
            if act == "add":
                g.pop(M.NOFIT, None)
            g[gid] = {"action": act, "date": date, "note": note, "group_name": groups[gid][0], "source_at_edit": M.source_at_edit(index, oid),
                      "batch": {"id": bid, "kind": kind, "threshold": thr if _num(thr) else None, "score": score, "source": source}}
        doc["revision"] += 1
        batches[bid] = {"date": date, "kind": kind, "threshold": thr if _num(thr) else None, "count": len(plan), "note": note, "undone": False, "replaced": replaced, "seq": doc["revision"],
                        "sig": [list(s) for s in sig]}
        doc["history"].append({"seq": doc["revision"], "date": date, "op": "batch", "batch": bid, "kind": kind, "n": len(plan), "note": note})
        doc["edits"] = {k: edits[k] for k in sorted(edits)}
        _backup(path, bid)
        M.write_atomic(path, doc)
        return {"ok": True, "batch": bid, "changed": True, "count": len(plan), "revision": doc["revision"]}


def _backup(path, bid):
    """a copy of the file as it was BEFORE this write, in corrections/backups/, the newest KEEP_BACKUPS kept."""
    if not os.path.exists(path):
        return
    d = os.path.join(os.path.dirname(path), "backups")
    os.makedirs(d, exist_ok=True)
    shutil.copyfile(path, os.path.join(d, "%s.before-%s.json" % (os.path.basename(path)[:-5], bid)))
    files = sorted((os.path.getmtime(os.path.join(d, f)), f) for f in os.listdir(d) if f.endswith(".json"))
    for _, f in files[:-KEEP_BACKUPS]:
        try:
            os.remove(os.path.join(d, f))
        except OSError:
            pass


def _undo(which, path, now=None):
    if not isinstance(which, str):
        raise M.ApiError(400, "undo takes a batch id or 'last'")
    with M.FileLock(path):
        try:
            doc = M.load_doc(path)
        except ValueError as exc:
            raise M.ApiError(500, str(exc) + " (not overwritten; fix or remove the file)")
        batches = doc.setdefault("batches", {})
        if which == "last":
            live = [(b.get("seq", 0), k) for k, b in batches.items() if not b.get("undone")]
            if not live:
                raise M.ApiError(404, "there is no batch to undo")
            which = max(live)[1]
        b = batches.get(which)
        if b is None:
            raise M.ApiError(404, "unknown batch: " + which)
        if b.get("undone"):
            return {"ok": True, "batch": which, "changed": False, "removed": 0, "restored": 0, "left_alone": 0, "revision": doc["revision"]}
        removed = left = restored = 0
        for oid in list(doc["edits"]):
            g = doc["edits"][oid]["groups"]
            for gid in list(g):
                bt = g[gid].get("batch")
                if bt and bt.get("id") == which:
                    del g[gid]
                    removed += 1
        for oid, rec in b.get("replaced", {}).items():
            e = doc["edits"].setdefault(oid, {"name": rec.get("name", ""), "groups": {}})
            for gid, old in rec["groups"].items():
                if gid not in e["groups"]:
                    e["groups"][gid] = old
                    restored += 1
                else:
                    left += 1
        for oid in list(doc["edits"]):
            if not doc["edits"][oid]["groups"]:
                del doc["edits"][oid]
        date = now or datetime.datetime.now().isoformat(timespec="seconds")
        b["undone"] = True
        b["undone_date"] = date
        doc["revision"] += 1
        doc["history"].append({"seq": doc["revision"], "date": date, "op": "batch-undo", "batch": which, "n": removed})
        _backup(path, "undo-" + which)
        M.write_atomic(path, doc)
        return {"ok": True, "batch": which, "changed": True, "removed": removed, "restored": restored, "left_alone": left, "revision": doc["revision"]}
