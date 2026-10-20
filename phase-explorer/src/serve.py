#!/usr/bin/env python3
"""Serve the explorer locally. The page fetches JSON, which file:// forbids.

    python src/serve.py [port]

Then open http://localhost:8765/reports/browse.html -- the branch/sub-branch/leaf
browsing page. The parse-audit explorer is at /reports/card-explorer.html.
"""
import datetime
import http.server
import json
import os
import socketserver
import sys
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual_common as MC
import manual_batch as MB
import group_search_log as GSL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
URL = f"http://localhost:{PORT}/reports/browse.html"
AUDIT_URL = f"http://localhost:{PORT}/reports/card-explorer.html"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):  # quieter: one line per request, no noise
        sys.stderr.write("%s %s\n" % (self.command, self.path))

    # ---- leaf phrase overrides ----------------------------------------
    # The phrase a leaf is labelled by is derived (src/leaf_phrases.py), and a
    # derived phrase is sometimes the wrong one to lead with. An override is
    # written HERE, to corrections/, and not into build/ -- build/ is
    # regenerated and would drop it. leaf_phrases.py reads this file back, so
    # an edit survives a rebuild and shows up in the report too.
    #
    # An override is free text: it is the user's wording, and the page marks it
    # as edited rather than passing it off as the cards' own.
    def do_phrase(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception as exc:
            self.send_error(400, f"bad JSON: {exc}")
            return

        leaf = body.get("leaf")
        if leaf is None or not str(leaf).lstrip("-").isdigit():
            self.send_error(400, "need a numeric leaf")
            return
        leaf = str(leaf)
        phrase = (body.get("phrase") or "").strip()

        path = os.path.join(ROOT, "corrections", "leaf_phrases.json")
        try:
            doc = json.load(open(path, encoding="utf-8"))
        except Exception:
            doc = {}
        doc.setdefault("_comment",
                       "Hand-written overrides for the phrase a leaf is "
                       "labelled by. Free text: this is the editor's wording, "
                       "not a verbatim card phrase, and the pages badge it as "
                       "edited. Delete an entry to fall back to the derived "
                       "phrase. Read by src/leaf_phrases.py. Hand-editable.")
        overrides = doc.setdefault("overrides", {})

        if phrase:
            overrides[leaf] = {
                "phrase": phrase,
                "was": body.get("was") or "",
                "when": datetime.datetime.now().isoformat(timespec="seconds"),
            }
        else:
            overrides.pop(leaf, None)   # empty box clears the override

        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, ensure_ascii=False)
        os.replace(tmp, path)

        out = json.dumps({"ok": True, "leaf": leaf, "phrase": phrase,
                          "total": len(overrides)}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    # ---- review-queue persistence -------------------------------------
    # The queue has to survive a rebuild, and the rebuild reads a FILE -- so a
    # decision cannot live in localStorage, or branch_leaves.py would never see
    # it and resolved entries would come straight back. One small endpoint is
    # the whole mechanism. Dev-only, bound to 127.0.0.1, same as the server.
    # ---- hand placements (corrections/manual_placements.json) -----------
    # POST /api/manual {oid, group, action: add|remove|nofit|clear, note}. The server validates against build/manual_index.json, fills source_at_edit and the date itself,
    # serializes the read-modify-write and writes through a temp file + rename. See src/manual_common.py. GET /api/manual/ping tells the page the endpoint exists.
    def send_json(self, status, obj):
        out = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(out)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(out)

    def local_host(self):
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        return host in ("localhost", "127.0.0.1", "::1")

    def do_GET(self):
        if self.path.split("?")[0].rstrip("/") == "/api/groupsearch/ping":
            self.send_json(200, {"ok": True, "enabled": GSL.enabled()})
            return
        if self.path.split("?")[0].rstrip("/") == "/api/manual/ping":
            idx = MC.load_index()
            try:
                rev = MC.load_doc()["revision"]
            except ValueError:
                rev = None
            self.send_json(200, {"ok": True, "enabled": idx is not None, "revision": rev, "batch": bool(idx and idx.get("batch"))})
            return
        super().do_GET()

    def do_manual(self):
        try:
            if not self.local_host():
                raise MC.ApiError(403, "local requests only")
            if self.headers.get("X-Manual-Edit") != "1" or "application/json" not in (self.headers.get("Content-Type") or ""):
                raise MC.ApiError(400, "need Content-Type: application/json and X-Manual-Edit: 1")
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise MC.ApiError(400, "bad Content-Length")
            if n > MC.MAX_BODY:
                self.rfile.read(min(n, 1 << 20))      # drain (bounded) so the client can read the 413 instead of a reset
                raise MC.ApiError(413, "body is %d bytes; the limit is %d" % (n, MC.MAX_BODY))
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception as exc:
                raise MC.ApiError(400, "bad JSON: %s" % exc)
            self.send_json(200, MC.apply_edit(body))
        except MC.ApiError as exc:
            self.send_json(exc.status, {"ok": False, "error": exc.msg})
        except Exception as exc:                      # never a silent failure: the page shows NOT SAVED with this text
            self.send_json(500, {"ok": False, "error": "server error: %s" % exc})

    # POST /api/manual/batch: place from suggestions / the fallback list, confirm or reject soft placements, or undo a batch. ALL OR NOTHING; see src/manual_batch.py. 404 when BATCH_ACTIONS is off.
    def do_batch(self):
        try:
            if not self.local_host():
                raise MC.ApiError(403, "local requests only")
            if self.headers.get("X-Manual-Edit") != "1" or "application/json" not in (self.headers.get("Content-Type") or ""):
                raise MC.ApiError(400, "need Content-Type: application/json and X-Manual-Edit: 1")
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise MC.ApiError(400, "bad Content-Length")
            if n > MB.MAX_BODY:
                self.rfile.read(min(n, 1 << 20))
                raise MC.ApiError(413, "body is %d bytes; the limit is %d" % (n, MB.MAX_BODY))
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception as exc:
                raise MC.ApiError(400, "bad JSON: %s" % exc)
            self.send_json(200, MB.apply_batch(body))
        except MC.ApiError as exc:
            self.send_json(exc.status, dict({"ok": False, "error": exc.msg}, **(exc.extra or {})))
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": "server error: %s" % exc})

    # POST /api/groupsearch/log {q, t: search|open, groups, cards}: what was typed in the main search box, for curating aliases. See src/group_search_log.py. 404 when GROUP_SEARCH is off.
    def do_groupsearch_log(self):
        try:
            if not GSL.enabled():
                raise MC.ApiError(404, "the group search is off")
            if not self.local_host():
                raise MC.ApiError(403, "local requests only")
            if self.headers.get("X-Manual-Edit") != "1" or "application/json" not in (self.headers.get("Content-Type") or ""):
                raise MC.ApiError(400, "need Content-Type: application/json and X-Manual-Edit: 1")
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise MC.ApiError(400, "bad Content-Length")
            if n > GSL.MAX_BODY:
                self.rfile.read(min(n, 1 << 20))
                raise MC.ApiError(413, "body is %d bytes; the limit is %d" % (n, GSL.MAX_BODY))
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception as exc:
                raise MC.ApiError(400, "bad JSON: %s" % exc)
            self.send_json(200, GSL.record(body))
        except MC.ApiError as exc:
            self.send_json(exc.status, {"ok": False, "error": exc.msg})
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": "server error: %s" % exc})

    def do_POST(self):
        route = self.path.rstrip("/")
        if route == "/api/groupsearch/log":
            self.do_groupsearch_log()
            return
        if route == "/api/manual":
            self.do_manual()
            return
        if route == "/api/manual/batch":
            self.do_batch()
            return
        if route == "/api/phrase":
            self.do_phrase()
            return
        if route != "/api/review":
            self.send_error(404, "no such endpoint")
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception as exc:
            self.send_error(400, f"bad JSON: {exc}")
            return

        key = body.get("key")
        action = body.get("action")
        # "split" means the finding was ACTED ON -- a sub-branch layer was built
        # for it -- as opposed to "reject", which means it was judged harmless.
        # Recording them as the same action would lose that distinction.
        if not key or action not in ("assign", "reject", "defer", "clear", "split"):
            self.send_error(400,
                            "need key and action assign|reject|defer|clear|split")
            return

        path = os.path.join(ROOT, "corrections", "branch_review.json")
        try:
            doc = json.load(open(path, encoding="utf-8"))
        except Exception:
            doc = {}
        doc.setdefault("_comment",
                       "Decisions from the branch review queue. 'assign' places "
                       "the leaf in that branch (marked manual); 'reject' means "
                       "it does not belong there and the entry never returns; "
                       "'split' means a sub-branch layer was built for it; "
                       "'defer' keeps it queued but out of the new-items view. "
                       "Hand-editable. Keys are '<leaf>|<candidate branch>'.")
        decisions = doc.setdefault("decisions", {})

        if action == "clear":
            decisions.pop(key, None)
        else:
            decisions[key] = {
                "action": action,
                "branch": body.get("branch") or "",
                "note": body.get("note") or "",
                "when": datetime.datetime.now().isoformat(timespec="seconds"),
            }

        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, ensure_ascii=False)
        os.replace(tmp, path)

        out = json.dumps({"ok": True, "key": key, "action": action,
                          "total": len(decisions)}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with Server(("127.0.0.1", PORT), Handler) as httpd:
        print(f"serving {ROOT}\n  {URL}\nCtrl-C to stop")
        if "--no-open" not in sys.argv:
            webbrowser.open(URL)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
