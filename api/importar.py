from __future__ import annotations

import json
import logging
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

import psycopg

from neon_storage import import_into_database
from local_server import parse_workbook


MAX_UPLOAD_BYTES = 4_500_000


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        stage = "procesar la carga"
        if urlparse(self.path).path != "/api/importar":
            self.send_json(404, {"error": "Ruta no encontrada."})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_UPLOAD_BYTES:
                raise UploadError("La carga está vacía o supera el límite de 4.5 MB.", 413)
            content_type = self.headers.get("Content-Type", "")
            if not content_type.lower().startswith("multipart/form-data"):
                raise UploadError("Envía ambos Excel usando el formulario de carga.")

            stage = "leer los archivos enviados"
            body = self.rfile.read(length)
            mime_message = BytesParser(policy=default).parsebytes(
                b"Content-Type: " + content_type.encode("ascii")
                + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
            )
            uploads = {}
            for part in mime_message.iter_parts():
                field = part.get_param("name", header="content-disposition")
                filename = Path(part.get_filename() or "").name
                payload = part.get_payload(decode=True) or b""
                if field in {"facts", "rules"} and filename:
                    uploads[field] = (filename, payload)

            if "facts" not in uploads or "rules" not in uploads:
                raise UploadError("Selecciona tanto Base_Hechos.xlsx como Base_Reglas.xlsx.")
            facts_name, facts_data = uploads["facts"]
            rules_name, rules_data = uploads["rules"]
            if not facts_name.lower().endswith(".xlsx") or not rules_name.lower().endswith(".xlsx"):
                raise UploadError("Los dos archivos deben estar en formato .xlsx.")

            stage = "validar la Base de hechos"
            facts = parse_workbook(facts_data, "facts", facts_name)
            stage = "validar la Base de reglas"
            rules = parse_workbook(rules_data, "rules", rules_name)
            stage = "guardar los datos en Neon"
            import_into_database(facts, rules, facts_name, rules_name)
            self.send_json(200, {"ok": True, "facts": len(facts), "rules": len(rules)})
        except UploadError as exc:
            self.send_json(exc.status, {"errors": [str(exc)]})
        except (ValueError, RuntimeError) as exc:
            self.send_json(400, {"errors": [str(exc)]})
        except psycopg.Error:
            self.send_json(503, {"errors": ["No se pudo guardar en Neon. Revisa la conexión de la base de datos."]})
        except Exception as exc:
            logging.exception("Error inesperado al importar las bases Excel")
            self.send_json(500, {"errors": [f"Error inesperado al {stage} ({type(exc).__name__}). Revisa los registros de Vercel."]})
            return

    def send_json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)


class UploadError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status
