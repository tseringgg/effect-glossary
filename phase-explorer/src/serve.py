#!/usr/bin/env python3
"""Serve the explorer locally. The page fetches JSON, which file:// forbids.

    python src/serve.py [port]

Then open http://localhost:8765/reports/card-explorer.html
"""
import datetime
import http.server
import json
import os
import socketserver
import sys
import webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
URL = f"http://localhost:{PORT}/reports/card-explorer.html"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):  # quieter: one line per request, no noise
        sys.stderr.write("%s %s\n" % (self.command, self.path))

    # ---- review-queue persistence -------------------------------------
    # The queue has to survive a rebuild, and the rebuild reads a FILE -- so a
    # decision cannot live in localStorage, or branch_leaves.py would never see
    # it and resolved entries would come straight back. One small endpoint is
    # the whole mechanism. Dev-only, bound to 127.0.0.1, same as the server.
    def do_POST(self):
        if self.path.rstrip("/") != "/api/review":
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
