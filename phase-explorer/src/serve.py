#!/usr/bin/env python3
"""Serve the explorer locally. The page fetches JSON, which file:// forbids.

    python src/serve.py [port]

Then open http://localhost:8765/reports/card-explorer.html
"""
import http.server
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
