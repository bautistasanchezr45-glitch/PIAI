from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

import psycopg

from neon_storage import get_database_status, get_knowledge_base


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            status = get_database_status()
            if not status["loaded"]:
                self.send_json(409, {"error": "Primero carga las bases de hechos y reglas."})
                return
            self.send_json(200, {"status": status, **get_knowledge_base()})
        except RuntimeError as exc:
            self.send_json(503, {"error": str(exc)})
        except psycopg.Error:
            self.send_json(503, {"error": "No se pudo consultar Neon."})

    def send_json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)
