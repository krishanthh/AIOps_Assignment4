#!/usr/bin/env python3
"""Persist actual Alertmanager notifications locally, without external messaging."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from datetime import datetime, timezone

LOG = Path(__file__).resolve().parents[1] / '.runtime' / 'alerts.jsonl'
LOG.parent.mkdir(exist_ok=True)

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/alerts':
            self.send_error(404)
            return
        size = int(self.headers.get('Content-Length', '0'))
        if size > 1_000_000:
            self.send_error(413)
            return
        try:
            payload = json.loads(self.rfile.read(size))
        except (ValueError, UnicodeDecodeError):
            self.send_error(400)
            return
        with LOG.open('a') as stream:
            stream.write(json.dumps({'received_at': datetime.now(timezone.utc).isoformat(), 'payload': payload}) + '\n')
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'ok')

ThreadingHTTPServer(('127.0.0.1', 9094), Handler).serve_forever()
