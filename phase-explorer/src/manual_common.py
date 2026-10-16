#!/usr/bin/env python3
"""Hand placements: the corrections file, its validation, the write path and the resolver. Shared by src/serve.py (the POST endpoint), src/build_manual_layer.py and the tests.

The ONE file this code ever writes is corrections/manual_placements.json. Nothing under build/ is edited here (the build script writes its own new files).

A hand edit is keyed (oracle_id, group id). Group ids are "<layer>:<id>": leaf, tent, loose, tag, kw (keyword block), rp (replacement block). Actions: add, remove, nofit ("nothing fits": group id none:fits).
"""
import datetime
import io
import json
import os
import re
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORR = os.environ.get("MANUAL_CORRECTIONS") or os.path.join(HERE, "corrections", "manual_placements.json")      # the env override is for the tests only
INDEX = os.path.join(HERE, "build", "manual_index.json")
NOFIT = "none:fits"
ACTIONS = ("add", "remove", "nofit", "clear")
LAYERS = ("leaf", "tent", "loose", "tag", "kw", "rp", "hand")
PRECISE = ("P", "B", "K", "R")                      # generated sources that are real placements
PRECISE_STATES = ("p", "b", "k", "g", "v")          # cards already placed (the 27,590)
SOFT_STATES = ("t", "a", "m")
MAX_BODY = 8192
MAX_NOTE = 500
MAX_EDITS = 50000
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
COMMENT = ("Hand placements, written by src/serve.py (POST /api/manual); hand-editable. Keyed by oracle_id, then group id (layer:id). action is add | remove | nofit "
           "(nofit = 'nothing fits', group id none:fits). source_at_edit is what the card's placement was when it was edited (filled by the server). 'clear' deletes an entry "
           "(undo); history keeps the trace. Read by src/build_manual_layer.py; the page reads this file directly.")
STATE_WORD = {"p": "placed", "b": "placed (broad groups only)", "k": "keyword block", "g": "replacement group", "v": "no abilities", "t": "tentative", "a": "annotation",
              "m": "community tag", "u": "unorganized", "o": "not a card"}
STATUS_WORD = {"p": "placed", "b": "broad", "k": "keyword", "g": "replacement", "v": "no_abilities", "t": "tentative", "a": "annotation", "m": "tag", "u": "unorganized", "o": "not_a_card"}
CAUSE_TEXT = {
    1: "no readable ability: the parser produced nothing the tool can group it on",
    2: "dropped-condition hold: an ability may be missing a condition, so it is held back",
    3: "gap-test hold: part of the card was not read, so its abilities are held back",
    4: "only in a catch-all: its abilities fit only a catch-all or 'less common effects' group",
    5: "only in a held group: its abilities fit only a loose group that was not promoted",
    6: "other",
    7: "gap-test stratum: one ability was read but another part of the card was not (card part not read)",
}
SRC_WORD = {"P": "precise", "B": "broad", "K": "keyword", "R": "replacement", "T": "tentative", "A": "annotation", "M": "tag", "L": "loose", "S": "sibling"}


class ApiError(Exception):
    def __init__(self, status, msg, extra=None):
        Exception.__init__(self, msg)
        self.status, self.msg, self.extra = status, msg, extra


# ------------------------------------------------------------------ files
def empty_doc():
    return {"_comment": COMMENT, "version": 1, "revision": 0, "edits": {}, "history": []}


def check_doc(doc):
    """schema check of the corrections file; raises ValueError naming the problem."""
    if not isinstance(doc, dict):
        raise ValueError("not an object")
    if not isinstance(doc.get("edits"), dict):
        raise ValueError("'edits' is missing or not an object")
    if not isinstance(doc.get("history", []), list):
        raise ValueError("'history' is not a list")
    if not isinstance(doc.get("batches", {}), dict):
        raise ValueError("'batches' is not an object")
    for oid, e in doc["edits"].items():
        if not isinstance(e, dict) or not isinstance(e.get("groups"), dict):
            raise ValueError("edit for %s has no 'groups' object" % oid)
        for gid, g in e["groups"].items():
            if not isinstance(g, dict) or g.get("action") not in ("add", "remove", "nofit"):
                raise ValueError("edit %s / %s has no valid action" % (oid, gid))
    return doc


def load_doc(path=None):
    """-> the doc, or a fresh empty one if the file does not exist. A file that exists but cannot be read or fails the schema raises ValueError: it is never overwritten."""
    path = path or CORR
    if not os.path.exists(path):
        return empty_doc()
    try:
        with io.open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except Exception as exc:
        raise ValueError("cannot read %s: %s" % (os.path.basename(path), exc))
    doc.setdefault("history", [])
    doc.setdefault("revision", 0)
    return check_doc(doc)


_index_cache = {"mtime": None, "path": None, "data": None}


def load_index(path=None):
    """build/manual_index.json (None if absent), cached by mtime."""
    path = path or INDEX
    if not os.path.exists(path):
        return None
    m = os.path.getmtime(path)
    if _index_cache["path"] != path or _index_cache["mtime"] != m:
        with io.open(path, encoding="utf-8") as fh:
            _index_cache.update(path=path, mtime=m, data=json.load(fh))
    return _index_cache["data"]


_thread_lock = threading.Lock()


class FileLock(object):
    """in-process lock plus a lock file (so a second server process cannot interleave a read-modify-write)."""

    def __init__(self, path):
        self.path = path + ".lock"

    def __enter__(self):
        _thread_lock.acquire()
        t0 = time.time()
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                return self
            except OSError:
                try:
                    if time.time() - os.path.getmtime(self.path) > 30:       # stale lock from a crashed process
                        os.remove(self.path)
                        continue
                except OSError:
                    pass
                if time.time() - t0 > 10:
                    _thread_lock.release()
                    raise ApiError(503, "the corrections file is locked by another process")
                time.sleep(0.02)

    def __exit__(self, *a):
        try:
            os.remove(self.path)
        except OSError:
            pass
        _thread_lock.release()


def write_atomic(path, doc):
    """temp file in the same folder, flushed and fsynced, then renamed over the target; the previous good file is kept as .bak."""
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=os.path.basename(path) + ".", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(doc, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        if os.path.exists(path):
            try:
                with io.open(path, "rb") as a, io.open(path + ".bak", "wb") as b:
                    b.write(a.read())
            except OSError:
                pass
        last = None
        for _ in range(5):
            try:
                os.replace(tmp, path)
                return
            except OSError as exc:                       # Windows: another process may hold the target for a moment
                last = exc
                time.sleep(0.05)
        raise ApiError(500, "could not replace the corrections file: %s" % last)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


# ------------------------------------------------------------------ the card's placement, as the server knows it
def source_at_edit(index, oid):
    c = index["cards"][oid]
    name, state, cause, gens = c[0], c[1], c[2], c[3]
    out = {"status": STATUS_WORD[state], "groups": [g[0] for g in gens]}
    if state in ("u", "t", "a", "m") and cause in CAUSE_TEXT:
        out["reason"] = {"code": cause, "text": CAUSE_TEXT[cause]}
    elif state in ("u", "t", "a", "m"):
        out["reason"] = {"code": 0, "text": "not yet organized in the build; shown only as " + STATE_WORD[state] if state != "u" else "not yet organized; cause not recorded"}
    return out


# ------------------------------------------------------------------ the resolver (canonical; reports/manualedit.js mirrors it and a test compares them)
def resolve(index, doc):
    """what the corrections file means against a build. Deterministic. Returns the counts, the per-card view and the orphans."""
    cards, groups = index["cards"], index["groups"]
    adds, removes, marks = {}, {}, {}
    orphans, renamed, stale = [], [], []
    for oid in sorted(doc["edits"]):
        e = doc["edits"][oid]
        c = cards.get(oid)
        for gid in sorted(e["groups"]):
            g = e["groups"][gid]
            act = g["action"]
            if c is None:
                orphans.append({"oid": oid, "name": e.get("name", ""), "group": gid, "action": act, "why": "card not in this build"})
                continue
            if act == "nofit":
                marks[oid] = g
                continue
            gi = groups.get(gid)
            if gi is None:
                orphans.append({"oid": oid, "name": c[0], "group": gid, "action": act, "group_name": g.get("group_name", ""), "why": "group not in this build"})
                continue
            if g.get("group_name") and g["group_name"] != gi[0]:
                renamed.append({"oid": oid, "name": c[0], "group": gid, "was": g["group_name"], "now": gi[0]})
            if act == "add":
                adds.setdefault(oid, {})[gid] = g
            else:
                held = [x for x in c[3] if x[0] == gid]
                if not held:
                    stale.append({"oid": oid, "name": c[0], "group": gid, "why": "the card no longer holds this group, so there is nothing to remove"})
                removes.setdefault(oid, {})[gid] = g
    for oid in list(marks):
        if oid in adds:
            del marks[oid]
    state_of = lambda o: cards[o][1]
    new, conf, prec = [], {"t": [], "a": [], "m": []}, []
    for oid in sorted(adds):
        s = state_of(oid)
        if s == "u":
            new.append(oid)
        elif s in SOFT_STATES:
            conf[s].append(oid)
        elif s in PRECISE_STATES:
            prec.append(oid)
    n_state = {}
    for c in cards.values():
        n_state[c[1]] = n_state.get(c[1], 0) + 1
    placed = sum(n_state.get(s, 0) for s in PRECISE_STATES)
    rec = {"placed": placed, "tentative": n_state.get("t", 0), "annotation": n_state.get("a", 0), "tag": n_state.get("m", 0), "hand": len(new),
           "unorganized": n_state.get("u", 0) - len(new), "not_cards": n_state.get("o", 0)}
    rec["sum"] = sum(rec.values())
    by_reason = {}
    for oid in new + sorted(marks):
        key = str((doc["edits"][oid]["groups"].get(NOFIT) or next(iter(adds.get(oid, {}).values()), {})).get("source_at_edit", {}).get("reason", {}).get("code", 0))
        by_reason.setdefault(("nofit:" if oid in marks else "hand:") + key, []).append(oid)
    bf = bool(index.get("batch"))
    isb = lambda o: all(v.get("batch") for v in adds[o].values())
    extra = ({"placed_by_hand_batch": sum(1 for o in new if isb(o)), "confirmed_by_hand_batch": sum(1 for v in conf.values() for o in v if isb(o)),
              "batch_removals": sum(1 for v in removes.values() for x in v.values() if x.get("batch")), "batches": len(doc.get("batches", {})),
              "batches_undone": sum(1 for b in doc.get("batches", {}).values() if b.get("undone"))} if bf else {})
    return {
        "counts": dict({"placed_by_hand_new": len(new), "confirmed_by_hand": sum(len(v) for v in conf.values()),
                   "confirmed_by_hand_of_which": {"tentative": len(conf["t"]), "annotation": len(conf["a"]), "tag": len(conf["m"])},
                   "precise_cards_with_edits_not_counted": len(prec), "marked_nothing_fits": len([o for o in marks if state_of(o) != "o"]),
                   "removals_recorded": sum(len(v) for v in removes.values()), "adds": sum(len(v) for v in adds.values()),
                   "orphans": len(orphans), "renamed": len(renamed), "stale_removals": len(stale)}, **extra),
        "reconciliation": rec,
        "hand_new": new, "confirmed": {k: v for k, v in conf.items()}, "precise_edits": prec, "marked": sorted(marks),
        "orphans": orphans, "renamed": renamed, "stale": stale,
        "by_reason": {k: sorted(v) for k, v in sorted(by_reason.items())},
        "adds": {o: sorted(v) for o, v in sorted(adds.items())}, "removes": {o: sorted(v) for o, v in sorted(removes.items())},
    }


# ------------------------------------------------------------------ the write path
def _clean_note(v):
    if v is None:
        return ""
    if not isinstance(v, str):
        raise ApiError(422, "note must be text")
    v = "".join(ch for ch in v if ch == "\n" or ch >= " ").strip()
    if len(v) > MAX_NOTE:
        raise ApiError(422, "note is %d characters; the limit is %d" % (len(v), MAX_NOTE))
    return v


def validate(body, index):
    """-> (oid, gid, action, note); raises ApiError. Checks the request against the build index only (not the file)."""
    if not isinstance(body, dict):
        raise ApiError(400, "body must be a JSON object")
    extra = set(body) - {"oid", "group", "action", "note"}
    if extra:
        raise ApiError(400, "unknown field(s): " + ", ".join(sorted(extra)))
    oid, gid, action = body.get("oid"), body.get("group"), body.get("action")
    if not isinstance(oid, str) or not UUID.match(oid):
        raise ApiError(400, "oid must be an oracle id")
    if action not in ACTIONS:
        raise ApiError(400, "action must be one of add | remove | nofit | clear")
    if not isinstance(gid, str) or ":" not in gid:
        raise ApiError(400, "group must look like layer:id")
    note = _clean_note(body.get("note"))
    card = index["cards"].get(oid)
    if card is None:
        raise ApiError(404, "unknown card: " + oid)
    if card[1] == "o":
        raise ApiError(422, "this entry is not a card in this tool; it cannot be placed")
    if action == "nofit" and gid != NOFIT:
        raise ApiError(400, "nofit uses group none:fits")
    if gid == NOFIT and action not in ("nofit", "clear"):
        raise ApiError(400, "none:fits only takes nofit or clear")
    if gid != NOFIT:
        if gid.split(":", 1)[0] not in LAYERS:
            raise ApiError(400, "unknown group layer in " + gid)
        gi = index["groups"].get(gid)
        if gi is None and action != "clear":
            raise ApiError(422, "unknown group: " + gid)
        if action == "add" and gi is not None and not gi[4]:
            raise ApiError(422, "this group is not offered for hand placement (a catch-all, a bucket or a retired hand-defined group)")
    return oid, gid, action, note


def apply_edit(body, index=None, path=None, now=None):
    """validate and apply one edit; returns the response dict. Raises ApiError. Serialized by a lock; written atomically."""
    index = index or load_index()
    if index is None:
        raise ApiError(503, "build/manual_index.json is missing; run python src/build_manual_layer.py")
    oid, gid, action, note = validate(body, index)
    path = path or CORR
    card = index["cards"][oid]
    with FileLock(path):
        try:
            doc = load_doc(path)
        except ValueError as exc:
            raise ApiError(500, str(exc) + " (not overwritten; fix or remove the file)")
        edits = doc["edits"]
        e = edits.get(oid)
        grp = (e or {}).get("groups", {})
        date = now or datetime.datetime.now().isoformat(timespec="seconds")
        entry, op, removed_flag = None, action, False
        if action == "clear":
            if gid in grp:
                del grp[gid]
                removed_flag = True
            op = "clear"
        elif action == "add":
            held = [x for x in card[3] if x[0] == gid and x[1] in PRECISE]
            if held:
                raise ApiError(409, "the card is already in this group (%s)" % SRC_WORD[held[0][1]])
            entry = {"action": "add", "date": date, "note": note, "group_name": index["groups"][gid][0], "source_at_edit": source_at_edit(index, oid)}
        elif action == "remove":
            held = [x for x in card[3] if x[0] == gid]
            if gid in grp and grp[gid]["action"] == "add" and not held:
                raise ApiError(409, "this group was added by hand; undo (clear) it instead of removing it")
            if not held:
                raise ApiError(422, "the card is not in this group, so there is nothing to remove")
            entry = {"action": "remove", "date": date, "note": note, "group_name": index["groups"][gid][0], "source_at_edit": source_at_edit(index, oid)}
        else:                                                    # nofit
            if any(g["action"] == "add" for g in grp.values()):
                raise ApiError(409, "the card has a hand placement; undo it before marking 'nothing fits'")
            entry = {"action": "nofit", "date": date, "note": note, "group_name": "", "source_at_edit": source_at_edit(index, oid)}
        if entry is not None:
            if e is None:
                if len(edits) >= MAX_EDITS:
                    raise ApiError(422, "too many edited cards")
                e = edits[oid] = {"name": card[0], "groups": {}}
                grp = e["groups"]
            grp[gid] = entry
            if action == "add" and NOFIT in grp:                 # placing a card ends its 'nothing fits' mark
                del grp[NOFIT]
                doc["history"].append({"seq": doc["revision"] + 1, "date": date, "op": "clear", "oid": oid, "group": NOFIT, "note": "placed by hand"})
        if e is not None and not grp:
            del edits[oid]
        if entry is None and not removed_flag:
            return {"ok": True, "revision": doc["revision"], "changed": False, "entry": None}
        doc["revision"] += 1
        doc["history"].append({"seq": doc["revision"], "date": date, "op": op, "oid": oid, "group": gid, "note": note})
        doc["edits"] = {k: edits[k] for k in sorted(edits)}
        write_atomic(path, doc)
        return {"ok": True, "revision": doc["revision"], "changed": True, "entry": entry, "name": card[0]}
