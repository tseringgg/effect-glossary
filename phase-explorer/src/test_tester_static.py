#!/usr/bin/env python3
"""Verify the tester view and its static export (headless Edge over the DevTools protocol; plain static servers only, never serve.py; GET only).

    python src/test_tester_static.py [--skip-throttle] [--keep]

Needs msedge.exe, `pip install websocket-client`, the build files, and writes only inside dist/ and dist.b/ (and temp folders).
Checks: protected files hashed before and after (corrections/, archive/, the shared JS, serve.py); two identical exports; the whitelist and the private-path scan, including planted files that must be
refused; hand_view.json re-derived independently from corrections; the six figures; ?dev=1 against the original browse.html (same DOM after the same steps, same requests, same hand counts); the
tester page on dist/ (search, group page, card click, tabs, tree, drawer at 390 px, the Report button and its clipboard fallback, no failed requests, no console errors, no POST, no endpoint, no
logging or editing UI); and a throttled first load. Clicks are DOM click() calls and the box is typed with real key events: no touch, no other browser.
"""
import gzip
import hashlib
import http.server
import json
import os
import re
import shutil
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

import websocket

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
DIST, DISTB = os.path.join(HERE, "dist"), os.path.join(HERE, "dist.b")
FIGURES = [73.3, 83.1, 89.5, 92.3, 92.8, 96.0]
RESULTS = []
NOTES = []
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + ((" -- " + str(detail)) if detail and not ok else (" (" + str(detail) + ")" if detail else "")))
    return ok


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def walk(root):
    out = []
    for r, ds, fs in os.walk(root):
        ds.sort()
        if r == root and ".git" in ds:
            ds.remove(".git")                         # dist/ may be a repository that is published from; it is not part of the export
        for f in sorted(fs):
            out.append(os.path.join(r, f))
    return out


def protected():
    files = walk(os.path.join(HERE, "corrections")) + walk(os.path.join(HERE, "archive"))
    files += [os.path.join(HERE, "reports", n) for n in ("abilityfind.js", "manualedit.js", "suggested.js", "groupsearch.js", "cardpin.js", "mergepage.js", "findcard.js", "cardview.js", "branchmap.js")]
    files += [os.path.join(HERE, "src", "serve.py")]
    files += [p for p in walk(os.path.join(HERE, "build")) if "/chunks/" not in p.replace("\\", "/") and os.path.dirname(p) == os.path.join(HERE, "build") and not p.endswith("group_search_log.json")]
    return {os.path.relpath(p, HERE).replace("\\", "/"): sha(p) for p in files if os.path.exists(p)}


# ---------------------------------------------------------------- servers (plain static: GET only; POST is answered 501 by the base class)
def free_port():
    k = socket.socket(); k.bind(("127.0.0.1", 0)); p = k.getsockname()[1]; k.close(); return p


class Srv(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    request_queue_size = 256
    daemon_threads = True

    def handle_error(self, *a):
        pass


def make_handler(root, gz=False, overrides=None, log=None):
    gzcache = {}

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=root, **k)

        def log_message(self, fmt, *args):
            if log is not None:
                log.append((self.command, self.path, args[1] if len(args) > 1 else ""))

        def do_GET(self):
            p = self.path.split("?")[0]
            if overrides and p in overrides:
                data = overrides[p]
                if isinstance(data, str):
                    data = data.encode("utf-8")
                    ctype = "application/javascript" if p.endswith(".js") else "text/html; charset=utf-8"
                else:
                    ctype = "text/html; charset=utf-8"
                self.send_response(200); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
                return
            if gz and "gzip" in (self.headers.get("Accept-Encoding") or ""):
                path = self.translate_path(self.path)
                if os.path.isfile(path) and not path.endswith((".png", ".jpg")):
                    if path not in gzcache:
                        gzcache[path] = gzip.compress(open(path, "rb").read(), 6, mtime=0)
                    data = gzcache[path]
                    ctype = self.guess_type(path)
                    self.send_response(200); self.send_header("Content-Type", ctype); self.send_header("Content-Encoding", "gzip"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
                    return
            super().do_GET()
    return H


class CDP:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=90, suppress_origin=True)
        self.n = 0
        self.events = []

    def call(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m.get("result", {})
            if "method" in m:
                self.events.append(m)

    def pump(self, secs):
        self.ws.settimeout(0.15)
        t = time.time()
        while time.time() - t < secs:
            try:
                m = json.loads(self.ws.recv())
                if "method" in m:
                    self.events.append(m)
            except websocket.WebSocketTimeoutException:
                pass
        self.ws.settimeout(90)

    def js(self, expr):
        try:
            r = self.call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        except websocket.WebSocketTimeoutException:
            raise RuntimeError("page did not answer within 90 s: " + expr[:160])
        if "exceptionDetails" in r:
            raise RuntimeError(r["exceptionDetails"].get("exception", {}).get("description", str(r["exceptionDetails"])))
        return r["result"].get("value")

    def wait(self, expr, secs=120):
        t = time.time()
        while time.time() - t < secs:
            try:
                if self.js(expr):
                    return True
            except Exception:
                pass
            self.pump(0.25)
        return False

    def type(self, text):
        for ch in text:
            self.call("Input.dispatchKeyEvent", type="keyDown", text=ch, key=ch)
            self.call("Input.dispatchKeyEvent", type="keyUp", key=ch)

    def key(self, key):
        self.call("Input.dispatchKeyEvent", type="keyDown", key=key, code=key, windowsVirtualKeyCode={"Escape": 27, "Enter": 13}.get(key, 0))
        self.call("Input.dispatchKeyEvent", type="keyUp", key=key, code=key, windowsVirtualKeyCode={"Escape": 27, "Enter": 13}.get(key, 0))


class Session:
    def __init__(self, root, path, width=1280, gz=False, overrides=None, throttle=None, cpu=None, height=None):
        self.log = []
        self.port, cdp = free_port(), free_port()
        self.srv = Srv(("127.0.0.1", self.port), make_handler(root, gz, overrides, self.log))
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.prof = tempfile.mkdtemp(prefix="tester_edge_")
        self.edge = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--user-data-dir=" + self.prof, "--remote-debugging-port=%d" % cdp, "--remote-allow-origins=*", "about:blank"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        tabs = None
        for _ in range(150):
            try:
                tabs = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json" % cdp)); break
            except Exception:
                time.sleep(0.2)
        pg = [t for t in tabs if t["type"] == "page"][0]
        self.c = CDP(pg["webSocketDebuggerUrl"])
        for d in ("Network", "Runtime", "Page", "Log"):
            self.c.call(d + ".enable")
        self.c.call("Network.setCacheDisabled", cacheDisabled=True)
        self.c.call("Emulation.setDeviceMetricsOverride", width=width, height=height or (844 if width < 500 else 900), deviceScaleFactor=1, mobile=width < 500)
        if throttle:
            kbps, lat = throttle
            self.c.call("Network.emulateNetworkConditions", offline=False, latency=lat, downloadThroughput=kbps * 1000 / 8, uploadThroughput=kbps * 1000 / 8)
        if cpu:
            self.c.call("Emulation.setCPUThrottlingRate", rate=cpu)
        self.t0 = time.time()
        self.c.call("Page.navigate", url="http://127.0.0.1:%d%s" % (self.port, path))

    def base(self):
        return "http://127.0.0.1:%d" % self.port

    def mark(self):
        return len(self.c.events)

    def net(self, mark=0):
        req, res, fin, fail = {}, {}, {}, {}
        for e in self.c.events[mark:]:
            m, p = e["method"], e["params"]
            if m == "Network.requestWillBeSent":
                req[p["requestId"]] = (p["request"]["method"], p["request"]["url"])
            elif m == "Network.responseReceived":
                res[p["requestId"]] = p["response"]["status"]
            elif m == "Network.loadingFinished":
                fin[p["requestId"]] = p["encodedDataLength"]
            elif m == "Network.loadingFailed":
                fail[p["requestId"]] = p.get("errorText")
        return [{"method": m, "url": u, "status": res.get(r), "bytes": fin.get(r), "failed": fail.get(r)} for r, (m, u) in req.items()]

    def console(self, mark=0):
        out = []
        for e in self.c.events[mark:]:
            m, p = e["method"], e["params"]
            if m == "Runtime.exceptionThrown":
                out.append("exception: " + str(p["exceptionDetails"].get("exception", {}).get("description") or p["exceptionDetails"].get("text"))[:200])
            elif m == "Runtime.consoleAPICalled" and p["type"] in ("error", "warning"):
                out.append(p["type"] + ": " + " ".join(str(a.get("value", a.get("description", ""))) for a in p["args"])[:200])
            elif m == "Log.entryAdded" and p["entry"]["level"] in ("error", "warning"):
                out.append("log " + p["entry"]["level"] + ": " + p["entry"]["text"][:160] + " " + p["entry"].get("url", "")[:100])
        return out

    def close(self):
        try:
            self.edge.kill()
        except Exception:
            pass
        self.srv.shutdown()
        shutil.rmtree(self.prof, ignore_errors=True)


FEATURE_FLAGS = ("TYPE_GROUPS", "NARROW_NO_CUT", "COLOUR_MODES", "FLIP_FACES", "ABILITY_TYPE_PAGES", "ABILITY_TYPE_FILTERS", "MODAL_ABILITIES", "BROAD_NARROWING", "PERSIST_FILTERS", "COLOUR_IDENTITY", "SEARCH_FIXES")          # the newer features (src/test_tester_features.py tests them on); this file tests the page as it was


def flags_off_text(extra_off=()):
    """reports/config.js with the four newer flags (and any extra named flag) switched off."""
    txt = open(os.path.join(HERE, "reports", "config.js"), encoding="utf-8").read()
    for f in FEATURE_FLAGS + tuple(extra_off):
        txt = re.sub(r"\b%s\s*:\s*true" % f, "%s: false" % f, txt)
    return txt


_CFG = []


def flags_off_config():
    if not _CFG:
        f = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
        f.write(flags_off_text()); f.close()
        _CFG.append(f.name)
    return _CFG[0]


def export(out, features=False):
    """Export the page. By default with the four newer features OFF (the page this file tests); features=True uses reports/config.js as it is."""
    cmd = [sys.executable, "-I", os.path.join(HERE, "src", "export_static.py"), "--out", os.path.relpath(out, HERE)] + ([] if features else ["--config", flags_off_config()])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=HERE)
    return r.returncode, r.stdout + r.stderr


def load_json(p):
    return json.load(open(p, encoding="utf-8"))


# ---------------------------------------------------------------- 1. exports, whitelist, private paths
def test_export():
    rc, out = export(DIST)
    check("export dist/ succeeds", rc == 0, out[-300:])
    rc2, out2 = export(DISTB)
    check("second export (dist.b/) succeeds", rc2 == 0, out2[-300:])
    m1, m2 = open(os.path.join(DIST, "manifest.json"), "rb").read(), open(os.path.join(DISTB, "manifest.json"), "rb").read()
    check("two exports: manifests byte-identical", m1 == m2)
    f1 = {os.path.relpath(p, DIST): sha(p) for p in walk(DIST)}
    f2 = {os.path.relpath(p, DISTB): sha(p) for p in walk(DISTB)}
    check("two exports: every file byte-identical (%d files)" % len(f1), f1 == f2, [k for k in set(f1) | set(f2) if f1.get(k) != f2.get(k)][:5])
    shutil.rmtree(DISTB)
    man = json.loads(m1.decode("utf-8"))
    rel = sorted(os.path.relpath(p, DIST).replace("\\", "/") for p in walk(DIST))
    check("manifest lists every file but itself", sorted([f["path"] for f in man["files"]] + ["manifest.json"]) == rel)
    check("manifest hashes match the files", all(sha(os.path.join(DIST, *f["path"].split("/"))) == f["sha256"] for f in man["files"]))
    r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "src", "export_static.py"), "--check", "--out", "dist", "--config", flags_off_config()], capture_output=True, text=True, cwd=HERE)
    check("export_static.py --check passes on dist/", r.returncode == 0, r.stdout + r.stderr)
    bad = [p for p in rel if any(x in p.lower().split("/")[:-1] for x in ("corrections", "backups", "archive", "data", "src", "logs")) or re.search(r"(\.bak|\.log|\.md|manual_placements|group_search_log|branch_review|hand_groups|group_aliases)", p)]
    check("dist/ has no corrections, backups, logs, archive, data, source or .md path", not bad, bad[:5])
    # every build file is a byte-for-byte copy of its source
    diff = [f["path"] for f in man["files"] if f["path"].startswith("build/") and f["path"] != "build/hand_view.json" and sha(os.path.join(HERE, *f["path"].split("/"))) != f["sha256"]]
    check("every exported build file is byte-identical to build/ (data unchanged)", not diff, diff[:3])
    # the whitelist, listed
    exact = [p for p in rel if not re.match(r"build/(suggested_cards/[gt]/|text_sug/l/)", p)]
    lazy = {}
    for p in rel:
        m = re.match(r"build/(suggested_cards/[gt]|text_sug/l)/", p)
        if m:
            lazy[m.group(1)] = lazy.get(m.group(1), 0) + 1
    NOTES.append("dist/ files (every one is on the whitelist): %d named files: %s; lazy: %s" % (len(exact), ", ".join(exact), lazy))
    check("every file in dist/ is on the whitelist (named %d + lazy %s)" % (len(exact), sorted(lazy.items())), len(exact) + sum(lazy.values()) == len(rel))
    return man


def test_hand_view():
    import export_static as ES
    d = json.loads(open(os.path.join(DIST, "build", "hand_view.json"), encoding="utf-8").read())
    check("hand_view.json keys are exactly adds, removes, nofit", set(d) == {"adds", "removes", "nofit"})
    corr = load_json(os.path.join(HERE, "corrections", "manual_placements.json"))
    adds = {}
    for oid, e in corr["edits"].items():
        for g, v in e["groups"].items():
            if v["action"] == "add":
                adds.setdefault(oid, []).append(g)
    adds = {o: sorted(v) for o, v in adds.items()}
    check("hand_view.adds equals an independent projection of corrections (%d cards, %d placements)" % (len(adds), sum(len(v) for v in adds.values())), d["adds"] == adds)
    raw = open(os.path.join(DIST, "build", "hand_view.json"), encoding="utf-8").read()
    check("hand_view.json holds no date, note, batch, history, score or name", not re.search(r"date|note|batch|history|score|source|name|2026", raw))
    for label, bad in (("an extra top-level field", {"adds": {}, "removes": {}, "nofit": [], "history": []}),
                       ("a date next to a group id", {"adds": {"002965be-a36f-4a09-9ce0-c6535bca1703": [{"gid": "leaf:a1", "date": "2026-10-15"}]}, "removes": {}, "nofit": []}),
                       ("a card name as a key", {"adds": {"Veil of Summer": ["leaf:a1"]}, "removes": {}, "nofit": []}),
                       ("a note string as a group", {"adds": {"002965be-a36f-4a09-9ce0-c6535bca1703": ["a note with spaces"]}, "removes": {}, "nofit": []})):
        try:
            ES.check_hand_view(bad)
            check("exporter refuses hand_view with " + label, False)
        except SystemExit:
            check("exporter refuses hand_view with " + label, True)
    # planted private files must stop the whitelist check
    tmp = tempfile.mkdtemp(prefix="plant_", dir=HERE)
    try:
        shutil.copytree(DIST, os.path.join(tmp, "d"), ignore=shutil.ignore_patterns("suggested_cards", "text_sug"))
        base = os.path.join(tmp, "d")
        for rel, body in (("corrections/manual_placements.json", "{}"), ("build/group_search_log.json", "{}"), ("archive/x.html", "x"), ("build/ability_taxonomy.json.bak", "x"), ("reports/notes.md", "x")):
            p = os.path.join(base, *rel.split("/")); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w").write(body)
        r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "src", "export_static.py"), "--check", "--out", base, "--config", flags_off_config()], capture_output=True, text=True, cwd=HERE)
        msg = r.stderr
        check("whitelist check refuses planted corrections/, log, archive, .bak and .md files", r.returncode != 0 and all(x in msg for x in ("corrections/manual_placements.json", "group_search_log.json", "archive/x.html", ".json.bak", "notes.md")), msg[:300])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_figures():
    t = load_json(os.path.join(DIST, "build", "ability_taxonomy.json"))["totals"]
    ten = load_json(os.path.join(DIST, "build", "tentative_placements.json"))["meta"]["headline"]
    ann = load_json(os.path.join(DIST, "build", "annotation_placements.json"))["meta"]["headline"]
    tag = load_json(os.path.join(DIST, "build", "tag_placements.json"))["meta"]["headline"]
    got = [t["headline"]["pct"], t["with_broad"]["pct"], ten["with_tentative"][1], ann["with_annotation"][1], ann["with_gap_stratum"][1], tag["with_tag"][1]]
    check("the six figures in dist/ data are unchanged %s" % got, got == FIGURES, got)


# ---------------------------------------------------------------- 2. ?dev=1 against the original page
SNAP = """(()=>{const g=id=>{const e=document.getElementById(id);if(!e)return '';const c=e.cloneNode(true);c.querySelectorAll('script').forEach(s=>s.remove());return c.outerHTML};return [document.title,g('panel'),g('tree'),document.querySelector('header').outerHTML,g('foot'),document.body.className].join('\\n=====\\n')})()"""


def dev_run(path, tmp_orig=None):
    ov = {}
    s = Session(HERE, path)
    c = s.c
    try:
        ok = c.wait("!!document.querySelector('#tree .row') && typeof HG !== 'undefined' && !!HG && !!SIB && !!SC && !!MI && !!CARDS && !!UNORG && !!LOOSE && !!TENT && !!TAGS && !!ANN && GSON === true && PINON === true && !!MERGED", 240)
        c.pump(3)
        snaps = {"boot": c.js(SNAP)}
        c.js("document.getElementById('q').focus()"); c.type("wrath")
        c.wait("document.querySelectorAll('#findres .gr, #findres .fr').length > 0", 90); c.pump(2.5)
        snaps["search"] = c.js(SNAP)
        c.js("(document.querySelector('#findres .gr')||{click(){}}).click()"); c.pump(4)
        snaps["group"] = c.js(SNAP)
        c.js("(document.querySelector('#sctabs button[data-sctab=matches]')||{click(){}}).click()"); c.pump(4)
        snaps["matches"] = c.js(SNAP)
        c.js("(document.querySelector('#sctabs button[data-sctab=members]')||{click(){}}).click()"); c.pump(1)
        c.js("(document.querySelector('.vbtn[data-view=images]')||{click(){}}).click()"); c.pump(3)
        snaps["images"] = c.js(SNAP)
        c.js("(document.querySelector('.lnk[data-go^=\"c:\"]')||{click(){}}).click()"); c.pump(5)
        snaps["cardpage"] = c.js(SNAP)
        hand = c.js("JSON.stringify({counts: MRES.counts, recon: MRES.reconciliation, hand_new: MRES.hand_new.slice().sort(), adds: Object.keys(MRES.adds).length})")
        reqs = sorted(set((r["method"], r["url"].replace(s.base(), "")) for r in s.net()))
        return {"ok": ok, "snaps": snaps, "hand": hand, "reqs": reqs, "console": s.console()}
    finally:
        s.close()


def test_dev_identity():
    orig = tempfile.mkdtemp(prefix="orig_")
    try:
        src = subprocess.run(["git", "show", "HEAD:phase-explorer/reports/browse.html"], capture_output=True, cwd=HERE)
        if src.returncode != 0:
            src = subprocess.run(["git", "show", "HEAD:reports/browse.html"], capture_output=True, cwd=HERE)
        check("original browse.html read from git HEAD", src.returncode == 0 and len(src.stdout) > 100000)
        open(os.path.join(orig, "browse_orig.html"), "wb").write(src.stdout)
        # the original page is served at /reports/browse_orig.html by a handler override
        global make_handler
        old_make = make_handler

        def patched(root, gz=False, overrides=None, log=None):
            ov = dict(overrides or {})
            ov["/reports/browse_orig.html"] = src.stdout.decode("utf-8")
            return old_make(root, gz, ov, log)
        make_handler = patched
        a = dev_run("/reports/browse_orig.html?dev=1")
        b = dev_run("/reports/browse.html?dev=1")
        make_handler = old_make
    finally:
        shutil.rmtree(orig, ignore_errors=True)
    check("?dev=1: both pages finished loading", a["ok"] and b["ok"])
    for k in a["snaps"]:
        same = a["snaps"][k] == b["snaps"][k]
        d = ""
        if not same:
            x, y = a["snaps"][k], b["snaps"][k]
            i = next((i for i in range(min(len(x), len(y))) if x[i] != y[i]), min(len(x), len(y)))
            d = "first difference at %d: %r vs %r" % (i, x[i - 40:i + 80], y[i - 40:i + 80])
        check("?dev=1 DOM identical to today's page after '%s' (%d chars)" % (k, len(a["snaps"][k])), same, d)
    noise = lambda u: u.startswith("edge://") or u.endswith("/favicon.ico")          # the browser's own requests, and a favicon fetch that races the page load
    ra = [(m, u.replace("/reports/browse_orig.html", "/reports/browse.html")) for m, u in a["reqs"] if not noise(u)]
    rb = [(m, u) for m, u in b["reqs"] if not noise(u)]
    check("?dev=1 makes the same requests as today's page (%d)" % len(ra), ra == rb, [x for x in set(ra) ^ set(rb)][:4])
    check("?dev=1 hand counts identical to today's page", a["hand"] == b["hand"], b["hand"][:200])
    norm = lambda L: [re.sub(r"127\.0\.0\.1:\d+", "HOST", x) for x in L if "favicon.ico" not in x]
    check("?dev=1 console identical to today's page", norm(a["console"]) == norm(b["console"]), norm(b["console"])[:3])
    return json.loads(b["hand"])


# ---------------------------------------------------------------- 3. the tester page on dist/
def visible(sel):
    return "(()=>{const e=document.querySelector(%s);return !!e && e.getClientRects().length>0 && getComputedStyle(e).visibility!=='hidden'})()" % json.dumps(sel)


def test_tester(dev_hand):
    s = Session(DIST, "/reports/browse.html", 1280)
    c = s.c
    try:
        ready = "typeof HG !== 'undefined' && !!HG && !!SIB && !!SC && !!MI && !!CARDS && !!UNORG && !!LOOSE && !!TENT && !!TAGS && !!ANN && GSON === true && PINON === true && !!MERGED"
        check("tester page boots on a plain static server", c.wait("document.body.classList.contains('tester') && " + ready, 240))
        c.pump(2)
        boot = s.net()
        names = [r["url"].replace(s.base(), "") for r in boot]
        check("boot: no request fails and none is an error status", all(not r["failed"] and (r["status"] or 0) < 400 for r in boot if r["url"].startswith(s.base())), [r for r in boot if r["failed"] or (r["status"] or 0) >= 400][:3])
        check("boot: only GET requests", all(r["method"] == "GET" for r in boot))
        check("boot: no /api/ and no corrections/ request", not [n for n in names if "/api/" in n or "corrections" in n], [n for n in names if "/api/" in n or "corrections" in n])
        check("boot: card_flags, queue, chunks and manual_suggestions are not requested", not [n for n in names if re.search(r"card_flags|queue\.json|chunks/|manual_suggestions|manual_fallback|text_sug/c/", n)])
        check("boot: keyword_facet.json is deferred", not [n for n in names if "keyword_facet" in n])
        check("boot: build/hand_view.json is requested", any(n.endswith("build/hand_view.json") for n in names))
        check("boot: no console errors or warnings", not s.console(), s.console()[:3])
        # presentation
        hidden_ids = ["cov", "prov", "handline", "sibline", "savebanner", "batchbar", "gsnote", "hidenopic", "showtent", "showann", "showtag", "showsib", "showbatch", "showhand", "tabs", "queuef", "cardf", "foot"]
        notvis = [i for i in hidden_ids if c.js(visible("#" + i))]
        check("old header, 7 switches, tabs, queue and card filters are not visible", not notvis, notvis)
        sw = c.js("['hidenopic','showtent','showann','showtag','showsib','showbatch'].map(i=>document.getElementById(i).checked).join()")
        check("switches stay at today's defaults (batch actions off: nothing edits)", sw == "true,true,true,true,false,false" or sw == "true,true,true,true,true,false", sw)
        check("search box is in the left column and the footer says Scryfall and fan content", c.js("!!document.querySelector('nav #q') && /Scryfall/.test(document.querySelector('.tfoot').innerText) && /Fan Content/.test(document.querySelector('.tfoot').innerText) && /Wizards of the Coast/.test(document.querySelector('.tfoot').innerText)"))
        check("Report a problem is on the page (top bar and footer)", c.js("document.querySelectorAll('a[data-report]').length >= 2"))
        # the tester page and dev page see the same hand placements
        th = c.js("JSON.stringify({counts: MRES.counts, recon: MRES.reconciliation, hand_new: MRES.hand_new.slice().sort(), adds: Object.keys(MRES.adds).length})")
        t = json.loads(th)
        check("hand placements: same hand_new set and cards with adds as the dev page", t["hand_new"] == dev_hand["hand_new"] and t["adds"] == dev_hand["adds"], (len(t["hand_new"]), len(dev_hand["hand_new"])))
        tc, dc = t["counts"], dev_hand["counts"]
        keys = ("placed_by_hand_new", "confirmed_by_hand", "confirmed_by_hand_of_which", "precise_cards_with_edits_not_counted", "marked_nothing_fits", "orphans")
        check("hand counts equal the dev page's (%s)" % {k: tc[k] for k in keys if k in tc and not isinstance(tc[k], dict)}, all(tc[k] == dc[k] for k in keys))
        check("reconciliation sums to 38,921", t["recon"]["sum"] == 38921 and t["recon"] == dev_hand["recon"], t["recon"])
        # ---- search
        mk = s.mark()
        c.js("document.getElementById('q').focus()"); c.type("board wipe")
        c.wait("document.querySelectorAll('#findres .gr').length > 0", 90); c.pump(1.5)
        ng = c.js("document.querySelectorAll('#findres .gr').length")
        check("search 'board wipe' lists groups in the left column (%d)" % ng, ng >= 1)
        check("results sit above the tree, tree folded while searching", c.js("document.getElementById('treewrap').classList.contains('folded') && document.querySelector('#findres').getBoundingClientRect().top < document.getElementById('treewrap').getBoundingClientRect().top"))
        check("search: group row has a name, a count and a one-line description", c.js("(()=>{const g=document.querySelector('#findres .gr');return !!g.querySelector('.gn') && !!g.querySelector('.gc') && !!g.querySelector('.gd')})()"))
        post = [r for r in s.net(mk) if r["method"] != "GET" or "/api/" in r["url"]]
        check("search sends nothing (no POST, no /api/)", not post, post)
        check("no logging UI (no 'logged' text, no Didn't find it? button)", c.js("!/logged on this computer|not logged/i.test(document.body.innerText) && !document.querySelector('[data-gsmiss]') && !/Didn.t find it/.test(document.body.innerText)"))
        c.js("document.querySelector('.sclr').click()"); c.pump(0.5)
        c.js("document.getElementById('q').focus()"); c.type("zzqxjv")
        c.wait("document.getElementById('findres').innerText.length > 0 && !/Loading/.test(document.getElementById('findres').innerText)", 60); c.pump(1)
        check("no result: 'Can't find it?' is a Report link, not a logging button", c.js("!!document.querySelector('#findres a[data-report=miss]') && !document.querySelector('#findres button[data-gsmiss]')"))
        c.js("document.querySelector('.sclr').click()"); c.pump(0.5)
        check("clearing the search unfolds the tree", c.js("!document.getElementById('treewrap').classList.contains('folded') && document.getElementById('findres').innerText===''"))
        # card search -> pin
        c.js("document.getElementById('q').focus()"); c.type("Wrath of God")
        c.wait("document.querySelectorAll('#findres .fr').length > 0", 60); c.pump(1)
        check("card search: a card row shows the groups it is in", c.js("/In:/.test(document.querySelector('#findres .fr').innerText)"), c.js("document.querySelector('#findres .fr').innerText"))
        c.js("document.querySelector('#findres .fr').click()"); c.wait("document.getElementById('pinwrap') && document.querySelector('.thead h1')", 60); c.pump(1)
        check("card result opens its group with the card pinned", c.js("!!document.getElementById('pinwrap') && /You searched for this card/.test(document.getElementById('pinwrap').textContent) && !!document.querySelector('.thead h1')"),
              c.js("'pinwrap=' + !!document.getElementById('pinwrap') + ' thead=' + !!document.querySelector('.thead h1') + ' tpend=' + document.getElementById('panel').classList.contains('tpend') + ' children=' + [...document.getElementById('panel').children].map(x=>x.id||x.className||x.tagName).join(',') + ' PINCUR=' + PINCUR + ' selected=' + selected + ' modal open=' + !document.querySelector('.tmodal').hidden + ' q=' + document.getElementById('q').value + ' row=' + (document.querySelector('#findres .fr')||{}).outerHTML"))
        c.js("document.querySelector('.sclr').click()"); c.pump(0.3)
        # ---- group page: a checked leaf, a broad leaf, a loose group
        info = c.js("""(()=>{const L=Object.entries(TAX.leaves);const ok=L.find(([id,l])=>!l.flags.length&&!(l.notes&&l.notes.length)&&memOids(id).length>20);const br=L.find(([id,l])=>l.flags.length&&memOids(id).length>20);return JSON.stringify({ok:ok&&ok[0],okname:ok&&ok[1].name,br:br&&br[0],brname:br&&br[1].name})})()""")
        info = json.loads(info)
        c.js("show('l:%s')" % info["ok"]); c.wait("document.querySelector('.thead h1') && document.querySelector('.thead h1').textContent===%s && document.querySelector('#list [data-oid]')" % json.dumps(info["okname"]), 60); c.pump(1)
        g = json.loads(c.js("""JSON.stringify({h1:document.querySelector('.thead h1').textContent,cnt:document.querySelector('.tcnt').textContent,note:!!document.querySelector('.tloosenote'),desc:!!document.querySelector('.tdesc'),tabs:[...document.querySelectorAll('#sctabs button')].map(b=>b.textContent),oldhead:document.querySelectorAll('#panel > h2, #panel > .note, #panel > p.sub').length,tiles:document.querySelectorAll('#list .tile').length,grid:document.getElementById('list').className})"""))
        check("checked group: name, count, no 'grouped loosely' note (%s, %s)" % (g["h1"], g["cnt"]), g["h1"] == info["okname"] and re.match(r"[\d,]+ cards", g["cnt"]) and not g["note"], g)
        check("group page: the old header, badges and notes are gone", g["oldhead"] == 0 and not c.js("!![...document.querySelectorAll('#panel .badge')].find(b=>b.getClientRects().length)"), g["oldhead"])
        check("group page: cards show as an image grid by default (%d tiles)" % g["tiles"], g["grid"] == "grid" and g["tiles"] > 0)
        gw = json.loads(c.js("""(()=>{const l=document.getElementById('list'),t=[...l.querySelectorAll('.tile')].slice(0,8).map(e=>e.getBoundingClientRect());return JSON.stringify({w:l.getBoundingClientRect().width,lefts:[...new Set(t.map(r=>Math.round(r.left)))].length,tw:t[0].width})})()"""))
        want = (gw["w"] - 30) / 4 * 0.75
        check("grid: four cards per row, each 75%% of a quarter, as on the developer page (%.1f px wide)" % gw["tw"], gw["lefts"] == 4 and abs(gw["tw"] - want) <= 1, (gw, want))
        check("page is named LogicVoid's Deck Doctor", c.js("document.title") == "LogicVoid’s Deck Doctor" and "Deck Doctor" in c.js("document.querySelector('.tbar .brand').textContent"))
        if g["tabs"]:
            check("tab is called 'Might also fit', never 'Possible matches'", g["tabs"][1].startswith("Might also fit (") and "Possible matches" not in c.js("document.getElementById('panel').innerText"), g["tabs"])
        c.js("show('l:%s')" % info["br"]); c.wait("document.querySelector('.thead h1') && document.querySelector('.thead h1').textContent===%s" % json.dumps(info["brname"]), 60); c.pump(1)
        check("broad group gets the same 'Grouped loosely' note", c.js("!!document.querySelector('.tloosenote') && /Grouped loosely/.test(document.querySelector('.tloosenote').innerText)"))
        tg = c.js("(()=>{const k=Object.keys(TENT.groups)[0];return k})()")
        c.js("show('tg:%s')" % tg); c.wait("document.querySelector('.thead .tloosenote')", 60); c.pump(1)
        check("tentative group: header with the same single note, no badge types", c.js("document.querySelectorAll('.thead .tloosenote').length===1"))
        # ---- card click -> modal
        c.js("show('l:%s')" % info["ok"]); c.wait("document.querySelector('#list .tile')", 60); c.pump(1)
        c.js("document.querySelector('#list .tile').click()")
        c.wait("document.querySelector('.tmodal:not([hidden]) .toracle')", 60); c.pump(1)
        m = json.loads(c.js("""(()=>{const mo=document.querySelector('.tmodal');const n=mo.querySelector('h2').textContent;const e=Object.entries(CARDS).find(([o,c])=>c.n===n);return JSON.stringify({name:n,oracle:mo.querySelector('.toracle').textContent,truth:e?e[1].t:null,img:(mo.querySelector('img')||{}).src||'',chips:mo.querySelectorAll('.chip').length,rep:!!mo.querySelector('a[data-report=card]')})})()"""))
        check("card click: modal with a large image, the card's own oracle text, its groups and a Report link", "/large/" in m["img"] and m["oracle"] == m["truth"] and m["chips"] >= 1 and m["rep"], m)
        c.key("Escape"); c.pump(0.5)
        check("Escape closes the card modal", c.js("document.querySelector('.tmodal').hidden===true"))
        # ---- tabs
        c.js("show('l:%s')" % info["ok"]); c.pump(2)
        tabsel = c.js("!!document.querySelector('#sctabs')")
        if not tabsel:
            gid = c.js("(()=>{const x=Object.entries(SC.groups).sort((a,b)=>b[1][1][0]-a[1][1][0])[0];return Suggested.gidOfKey?x[0]:x[0]})()")
            c.js("show('%s')" % c.js("Manual.goKey(%s)" % json.dumps(gid))); c.wait("document.querySelector('#sctabs')", 60); c.pump(1)
        c.js("document.querySelector('#sctabs button[data-sctab=matches]').click()"); c.wait("document.getElementById('suggsec') && !document.getElementById('suggsec').classList.contains('sc-off') && document.querySelector('#suggsec .sgrow, #suggsec .sub')", 60); c.pump(2)
        tabtxt = c.js("document.getElementById('suggsec').innerText")
        check("Might also fit tab: rows, no Add, no Undo, no slider, no tick, no score", c.js("!document.querySelector('#suggsec [data-sact=add], #suggsec [data-sact=undo], #suggsec input[type=range], #suggsec input[type=checkbox]')") and "Floor" not in tabtxt and "Add" not in c.js("[...document.querySelectorAll('#suggsec button')].map(b=>b.textContent).join(' ')"), tabtxt[:120])
        check("tab says suggested, not checked", "Suggested, not checked" in tabtxt or "hint, not a placement" in tabtxt)
        c.js("document.querySelector('#sctabs button[data-sctab=members]').click()"); c.pump(1)
        check("switching back shows the group's own cards", c.js("document.getElementById('suggsec').classList.contains('sc-off') && !document.getElementById('list').classList.contains('sc-off')"))
        # ---- tree
        mk = s.mark()
        c.js("document.querySelector('#tree .row[data-k^=\"f:\"]').click()"); c.pump(1)
        check("tree: a family opens", c.js("document.querySelectorAll('#tree .row.l2').length > 0"))
        names0 = [r["url"] for r in s.net()]
        c.js("if (!open.has('GL:')) document.querySelector('#tree .row[data-k=\"GL:\"]').click()"); c.pump(0.5)
        check("tree: 'Grouped loosely' folds open to tentative, held-condition, effect and tag groups", c.js("[...document.querySelectorAll('#tree .blk.sub2')].map(e=>e.textContent).join('|')").count("|") >= 2, c.js("[...document.querySelectorAll('#tree .blk.sub2')].map(e=>e.textContent).join('|')"))
        c.js("document.querySelector('#tree .row[data-k=\"NG:\"]').click()"); c.pump(0.5)
        check("tree: 'Cards not grouped yet' is collapsed, then lists the not-yet-organized groups", c.js("document.querySelectorAll('#tree .row[data-k^=\"u:\"]').length > 0 && !!document.querySelector('#tree .row[data-k=\"UR:\"]')"))
        c.js("document.querySelector('#tree .row[data-k^=\"u:\"]').click()"); c.wait("/Not grouped yet/.test((document.querySelector('.thead h1')||{}).textContent||'')", 60); c.pump(1)
        check("a not-grouped-yet page opens with the same header form", c.js("!!document.querySelector('.thead h1') && !!document.querySelector('.tcnt')"))
        before = len([r for r in s.net() if "keyword_facet" in r["url"]])
        c.js("document.querySelector('#tree .row[data-k=\"Y:\"]').click()"); c.wait("document.querySelector('#tree .row[data-k^=\"yk:\"]')", 60); c.pump(1)
        check("tree: keyword facet loads only when 'By keyword' is opened (%d before, %d after)" % (before, len([r for r in s.net() if "keyword_facet" in r["url"]])), before == 0 and any("keyword_facet" in r["url"] for r in s.net()))
        c.js("document.querySelector('#tree .row[data-k=\"hg:%s\"], #tree .row[data-k^=\"hg:\"]').click()" % "x"); c.wait("document.querySelector('.thead h1')", 30); c.pump(1)
        # ---- Cards tab hidden, #C: ignored
        check("Cards and To place tabs are not visible", not c.js(visible("#tabs")) and not c.js(visible("#cardf")))
        c.js("location.hash = '#C%3A'"); c.pump(1.5)
        check("a pasted #C: link does not open the card list or hide the tree", c.js("MODE==='abilities' && !document.getElementById('tree').hidden && !document.getElementById('cardf').offsetParent"))
        # ---- how this works: figures from data
        c.js("document.getElementById('thow').click()"); c.pump(0.8)
        how = c.js("document.querySelector('.tmodal:not([hidden])') ? document.querySelector('.tmodal').innerText : ''")
        found = [f for f in FIGURES if ("%s%%" % f) in how]
        check("How this works shows the honest note and all six figures read from the data %s" % found, len(found) == 6 and "best guess" in how and "source of truth" in how, how[:200])
        check("How this works credits Scryfall and carries the fan-content line", "Scryfall" in how and "Fan Content" in how)
        c.key("Escape"); c.pump(0.3)
        # ---- whole run
        allnet = s.net()
        bad = [r for r in allnet if r["url"].startswith(s.base()) and (r["failed"] or (r["status"] or 0) >= 400)]
        check("whole run: no failed or error same-origin request (%d requests)" % len(allnet), not bad, bad[:3])
        check("whole run: no POST, no /api/, no corrections/ request", not [r for r in allnet if r["method"] != "GET" or "/api/" in r["url"] or "corrections" in r["url"]])
        ext = [r for r in allnet if not r["url"].startswith(s.base())]
        check("whole run: the only outside requests are Scryfall images (%d)" % len(ext), all(r["url"].startswith("https://cards.scryfall.io/") for r in ext), [r["url"] for r in ext if not r["url"].startswith("https://cards.scryfall.io/")][:3])
        ef = [r for r in ext if r["failed"] or (r["status"] or 0) >= 400]
        if ef:
            NOTES.append("%d Scryfall image requests failed or errored in the desktop run" % len(ef))
        con = [x for x in s.console() if not re.search(r"cards\.scryfall\.io", x)]
        check("whole run: no console errors or warnings", not con, con[:3])
        served_post = [x for x in s.log if x[0] != "GET"]
        check("the static server saw no non-GET request", not served_post, served_post[:3])
    finally:
        s.close()


def test_phone():
    s = Session(DIST, "/reports/browse.html", 390)
    c = s.c
    try:
        c.wait("document.body.classList.contains('tester') && typeof HG !== 'undefined' && !!HG && !!SIB && !!SC && !!MI && !!CARDS", 240); c.pump(2)
        r = json.loads(c.js("""(()=>{const n=document.querySelector('nav').getBoundingClientRect(),m=document.getElementById('tmenu').getBoundingClientRect();return JSON.stringify({navRight:n.right,menu:[m.width,m.height],sw:document.documentElement.scrollWidth,pw:document.getElementById('panel').scrollWidth})})()"""))
        check("390 px: the left column is off-screen until opened", r["navRight"] <= 1, r)
        check("390 px: the Find button is 44 px or more and the page has no sideways scroll", r["menu"][0] >= 44 and r["menu"][1] >= 44 and r["sw"] <= 390 and r["pw"] <= 390, r)
        c.js("document.getElementById('tmenu').click()"); c.pump(0.6)
        r = json.loads(c.js("""(()=>{const n=document.querySelector('nav').getBoundingClientRect(),q=document.getElementById('q').getBoundingClientRect();return JSON.stringify({navLeft:n.left,navRight:n.right,qh:q.height,drawer:document.body.classList.contains('drawer-open'),exp:document.getElementById('tmenu').getAttribute('aria-expanded')})})()"""))
        check("390 px: the Find button opens the left column as a slide-over", r["drawer"] and r["navLeft"] >= -1 and r["navRight"] <= 390 and r["exp"] == "true", r)
        c.js("document.getElementById('q').focus()"); c.type("board wipe")
        c.wait("document.querySelectorAll('#findres .gr').length > 0", 90); c.pump(1.5)
        r = json.loads(c.js("""(()=>{const g=[...document.querySelectorAll('#findres .gr')].map(e=>e.getBoundingClientRect().height);const t=[...document.querySelectorAll('.sclr, #q')].map(e=>e.getBoundingClientRect().height);return JSON.stringify({g:g,t:t,sw:document.documentElement.scrollWidth})})()"""))
        check("390 px: results and the search box are 44 px or taller, no sideways scroll", min(r["g"]) >= 44 and min(r["t"]) >= 44 and r["sw"] <= 390, r)
        q0 = c.js("document.getElementById('q').value"); n0 = c.js("document.querySelectorAll('#findres .gr').length")
        c.js("document.querySelectorAll('#findres .gr')[1].click()"); c.wait("document.querySelector('.thead h1') && document.querySelector('#list [data-oid]') && !document.querySelector('#panel.tpend')", 90); c.pump(1.5)
        check("390 px: picking a result closes the drawer and shows the group", c.js("!document.body.classList.contains('drawer-open') && !!document.querySelector('.thead h1')"))
        c.js("document.getElementById('tmenu').click()"); c.pump(0.5)
        check("390 px: reopening shows the same query and results", c.js("document.getElementById('q').value") == q0 and c.js("document.querySelectorAll('#findres .gr').length") == n0, (q0, n0))
        c.key("Escape"); c.pump(0.4)
        check("390 px: Escape closes the drawer", c.js("!document.body.classList.contains('drawer-open')"))
        r = json.loads(c.js("""(()=>{const t=[...document.querySelectorAll('#list .tile')].slice(0,6).map(e=>Math.round(e.getBoundingClientRect().left));return JSON.stringify({lefts:[...new Set(t)],sw:document.documentElement.scrollWidth,tabs:[...document.querySelectorAll('#sctabs button')].map(b=>b.getBoundingClientRect().height),h1:document.querySelector('.thead h1').getBoundingClientRect().right})})()"""))
        check("390 px: cards go two across, tabs are 44 px, no sideways scroll", len(r["lefts"]) == 2 and r["sw"] <= 390 and all(h >= 44 for h in r["tabs"]) and r["h1"] <= 390, r)
        # card -> modal -> Report with the clipboard refused
        c.js("document.querySelector('#list .tile').click()"); c.wait("document.querySelector('.tmodal:not([hidden]) .toracle')", 60); c.pump(1)
        r = json.loads(c.js("""(()=>{const b=document.querySelector('.tbox').getBoundingClientRect();return JSON.stringify({l:b.left,r:b.right,bottom:b.bottom,h:b.height,sw:document.documentElement.scrollWidth,card:document.querySelector('.tmodal h2').textContent,x:document.querySelector('.tclose').getBoundingClientRect().height})})()"""))
        check("390 px: the card sheet fits the screen (width %.0f)" % (r["r"] - r["l"]), r["l"] >= 0 and r["r"] <= 390 and r["sw"] <= 390 and r["x"] >= 44, r)
        card = r["card"]
        grp = c.js("document.querySelector('.thead h1').textContent")
        stub = """window.__href=null;window.__copied=null;window.addEventListener('click',e=>{const a=e.target.closest&&e.target.closest('a[data-report]');if(a){window.__href=a.href;e.preventDefault()}},false);
                  window.__mode='%s'; Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:t=>{ if(window.__mode==='refuse') return Promise.reject(new Error('denied')); window.__copied=t; return Promise.resolve() }}});
                  document.execCommand=()=>false; 1"""
        c.js(stub % "refuse")
        c.js("document.querySelector('.tmodal a[data-report=card]').click()"); c.wait("document.getElementById('treptext')", 20); c.pump(0.5)
        r = json.loads(c.js("""(()=>{const t=document.getElementById('treptext'),b=document.querySelector('.tbox').getBoundingClientRect();return JSON.stringify({text:t.value,sel:[t.selectionStart,t.selectionEnd,t.value.length],l:b.left,r:b.right,sw:document.documentElement.scrollWidth,href:window.__href,focus:document.activeElement===t})})()"""))
        check("Report, clipboard refused at 390 px: a copy box opens with the report selected", r["sel"][0] == 0 and r["sel"][1] == r["sel"][2] > 0 and r["focus"], r["sel"])
        check("Report text names the card, the group and the page", ("Card: " + card) in r["text"] and ("Group: " + grp) in r["text"] and "Page: http://127.0.0.1" in r["text"], r["text"])
        check("Report copy box fits 390 px, no sideways scroll", r["l"] >= 0 and r["r"] <= 390 and r["sw"] <= 390, r)
        check("Report link goes to the feedback URL from config.js", r["href"] == re.search(r'feedbackUrl:\s*"([^"]+)"', open(os.path.join(HERE, "reports", "config.js"), encoding="utf-8").read()).group(1), r["href"])
        c.key("Escape"); c.pump(0.4)
        c.js(stub % "ok")
        c.js("document.querySelector('.tfoot a[data-report]').click()"); c.pump(1)
        r = json.loads(c.js("JSON.stringify({copied:window.__copied,toast:document.querySelector('.ttoast').hidden?'':document.querySelector('.ttoast').textContent})"))
        check("Report, clipboard allowed: the report is copied and a note says so", r["copied"] and "Group: " + grp in r["copied"] and "Card: (none)" in r["copied"] and "copied" in r["toast"], r)
        con = [x for x in s.console() if not re.search(r"cards\.scryfall\.io", x)]
        check("390 px run: no console errors", not con, con[:3])
        bad = [r for r in s.net() if r["url"].startswith(s.base()) and (r["failed"] or (r["status"] or 0) >= 400)]
        check("390 px run: no failed same-origin request", not bad, bad[:3])
    finally:
        s.close()
    # query mode: a config that pre-fills the address instead of the clipboard
    cfg = 'window.APP_CONFIG={feedbackUrl:"http://example.invalid/new",prefill:"query",titleParam:"title",bodyParam:"body"};'
    s = Session(DIST, "/reports/browse.html", 1280, overrides={"/reports/config.js": cfg})
    c = s.c
    try:
        c.wait("document.body.classList.contains('tester') && !!MI", 240); c.pump(1)
        c.js("window.addEventListener('click',e=>{const a=e.target.closest&&e.target.closest('a[data-report]');if(a){window.__href=a.href;e.preventDefault()}},false)")
        c.js("document.querySelector('.tbar a[data-report]').click()")
        h = c.js("window.__href")
        check("config prefill=query puts title and body in the address", bool(h) and h.startswith("http://example.invalid/new?title=") and "&body=" in h and "Problem%20report" in h, h)
    finally:
        s.close()


def test_throttled():
    out = {}
    for label, kbps, lat, cpu in (("mid-range phone on 4G (9 Mbps, 170 ms, 4x CPU)", 9000, 170, 4), ("slow 4G reference (1.6 Mbps, 150 ms, 4x CPU)", 1600, 150, 4)):
        s = Session(DIST, "/reports/browse.html", 390, gz=True, throttle=(kbps, lat), cpu=cpu)
        c = s.c
        try:
            t0 = time.time()
            ready = "document.body.classList.contains('tester') && typeof HG !== 'undefined' && !!HG && !!SIB && !!SC && !!MI && !!CARDS && !!UNORG && !!LOOSE && !!TENT && !!TAGS && !!ANN"
            tree = c.wait("!!document.querySelector('#tree .row')", 600); t_tree = time.time() - t0
            ok = c.wait(ready, 900); t_ready = time.time() - t0
            c.pump(1)
            boot = [r for r in s.net() if r["url"].startswith(s.base())]
            tb = sum(r["bytes"] or 0 for r in boot)
            t1 = time.time()
            c.js("document.getElementById('tmenu').click()"); c.js("document.getElementById('q').focus()"); c.type("board wipe")
            c.wait("document.querySelectorAll('#findres .gr').length > 0", 900); t_search = time.time() - t1
            t2 = time.time()
            c.js("document.querySelectorAll('#findres .gr')[0].click()")
            c.wait("document.querySelector('#list [data-oid]') && !document.querySelector('#panel.tpend')", 900); t_group = time.time() - t2
            allb = sum(r["bytes"] or 0 for r in s.net() if r["url"].startswith(s.base()))
            out[label] = {"tree_visible_s": round(t_tree, 1), "ready_s": round(t_ready, 1), "ok": ok, "boot_requests": len(boot), "boot_bytes_on_wire": tb, "first_search_s": round(t_search, 1), "first_group_s": round(t_group, 1), "total_bytes_on_wire": allb}
            print(label, out[label])
        finally:
            s.close()
    return out


def main():
    skip_throttle = "--skip-throttle" in sys.argv
    before = protected()
    git0 = subprocess.run(["git", "status", "--short", "--", "."], capture_output=True, text=True, cwd=HERE).stdout
    test_export()
    test_hand_view()
    test_figures()
    dev_hand = test_dev_identity()
    test_tester(dev_hand)
    test_phone()
    thr = None if skip_throttle else test_throttled()
    after = protected()
    changed = [k for k in set(before) | set(after) if before.get(k) != after.get(k)]
    check("protected files byte-identical before and after (%d hashed: corrections/, archive/, shared JS, serve.py, top-level build files)" % len(before), not changed, changed[:5])
    if os.path.exists(DISTB):
        shutil.rmtree(DISTB)
    print("\n%d checks, %d failed" % (len(RESULTS), len([r for r in RESULTS if not r[1]])))
    for n in NOTES:
        print("NOTE", n)
    if thr:
        print("THROTTLED", json.dumps(thr, indent=1))
    print("git status (project):\n" + subprocess.run(["git", "status", "--short", "--", "."], capture_output=True, text=True, cwd=HERE).stdout)
    sys.exit(1 if any(not r[1] for r in RESULTS) else 0)


if __name__ == "__main__":
    main()
