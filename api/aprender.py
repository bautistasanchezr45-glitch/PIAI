from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

import psycopg

from neon_storage import get_database_status, save_learning_case


OPTIONS = {
    "temperature": {"Correcta", "Fuera de especificación"},
    "pressure": {"Correcta", "Incorrecta"},
    "time": {"Adecuado", "Inadecuado"},
    "rawMaterial": {"Conforme", "No conforme"},
    "machineSettings": {"Correctos", "Incorrectos"},
}
RISKS = {"Bajo", "Medio", "Alto", "Muy alto"}
ACTIONS = {"Continuar producción", "Ajustar parámetros", "Inspeccionar producto", "Retener lote", "Detener proceso"}


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 16_000:
                self.send_json(413, {"error": "La solicitud está vacía o excede el límite permitido."})
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Completa las cinco condiciones y el resultado observado.")
            inputs = {key: payload.get(key) for key in OPTIONS}
            if any(inputs[key] not in allowed for key, allowed in OPTIONS.items()):
                raise ValueError("Completa las cinco condiciones con una opción válida.")
            risk = payload.get("observedRisk")
            action = payload.get("observedAction")
            if risk not in RISKS or action not in ACTIONS:
                raise ValueError("Selecciona un riesgo y una acción observados válidos.")
            if not get_database_status()["loaded"]:
                self.send_json(409, {"error": "Primero carga las bases de hechos y reglas."})
                return
            case_id = save_learning_case(inputs, risk, action)
            self.send_json(201, {"ok": True, "id": case_id})
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self.send_json(400, {"error": str(exc)})
        except RuntimeError as exc:
            self.send_json(503, {"error": str(exc)})
        except psycopg.Error:
            self.send_json(503, {"error": "No se pudo guardar el caso aprendido en Neon."})

    def send_json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)
