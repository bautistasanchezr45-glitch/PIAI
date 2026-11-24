from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

import psycopg

from neon_storage import get_database_status


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            result = get_database_status()
            self.send_json(200, result)
        except RuntimeError as exc:
            self.send_json(503, {"loaded": False, "error": str(exc)})
        except psycopg.Error:
            self.send_json(503, {"loaded": False, "error": "No se pudo conectar con Neon."})

    def send_json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)
