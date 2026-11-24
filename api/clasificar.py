from __future__ import annotations

import json
import unicodedata
from http.server import BaseHTTPRequestHandler

import psycopg

from neon_storage import find_matching_fact, get_database_status


MAX_BODY_BYTES = 16_000
OPTIONS = {
    "temperature": {"Correcta", "Fuera de especificación"},
    "pressure": {"Correcta", "Incorrecta"},
    "time": {"Adecuado", "Inadecuado"},
    "rawMaterial": {"Conforme", "No conforme"},
    "machineSettings": {"Correctos", "Incorrectos"},
}


def classify_pseint(inputs: dict[str, str]) -> tuple[str, str, str]:
    temperature = inputs["temperature"]
    pressure = inputs["pressure"]
    operation_time = inputs["time"]
    raw_material = inputs["rawMaterial"]
    machine_settings = inputs["machineSettings"]

    if raw_material == "No conforme" and machine_settings == "Incorrectos":
        risk = "Muy alto"
        reason = "Materia prima no conforme y ajustes de máquina incorrectos."
    elif (temperature == "Fuera de especificación" and pressure == "Incorrecta") or (
        operation_time == "Inadecuado" and machine_settings == "Incorrectos"
    ):
        risk = "Muy alto"
        reason = "Se detectó una combinación crítica de desviaciones del proceso."
    elif (
        temperature == "Correcta"
        and pressure == "Correcta"
        and operation_time == "Adecuado"
        and raw_material == "Conforme"
        and machine_settings == "Correctos"
    ):
        risk = "Bajo"
        reason = "Los cinco parámetros están dentro de las condiciones esperadas."
    elif (
        (temperature == "Fuera de especificación" or pressure == "Incorrecta")
        and operation_time == "Adecuado"
        and raw_material == "Conforme"
        and machine_settings == "Correctos"
    ):
        risk = "Medio"
        reason = "Hay una desviación de temperatura o presión; los demás parámetros son adecuados."
    elif (
        temperature == "Fuera de especificación"
        or pressure == "Incorrecta"
        or operation_time == "Inadecuado"
    ):
        risk = "Alto"
        reason = "Una o más condiciones del proceso están fuera de lo esperado."
    else:
        return "Indefinida", "Sin determinar", "La combinación no coincide con una rama del árbol PSeInt."

    if risk == "Bajo":
        action = "Continuar producción"
    elif risk == "Medio":
        action = "Ajustar parámetros"
    elif risk == "Alto":
        action = "Inspeccionar producto"
    elif raw_material == "No conforme":
        action = "Retener lote"
    elif machine_settings == "Incorrectos" and pressure == "Incorrecta":
        action = "Detener proceso"
    else:
        action = "Retener lote"
    return risk, action, reason


def comparable(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold()


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/clasificar":
            self.send_json(404, {"error": "Ruta no encontrada."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY_BYTES:
                self.send_json(413, {"error": "La solicitud está vacía o excede el límite permitido."})
                return
            inputs = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(inputs, dict):
                raise ValueError("Envía las cinco condiciones del proceso.")
            for key, allowed in OPTIONS.items():
                if inputs.get(key) not in allowed:
                    raise ValueError("Completa las cinco condiciones con una opción válida.")

            status = get_database_status()
            if not status["loaded"]:
                self.send_json(409, {"error": "Primero carga Base_Hechos.xlsx y Base_Reglas.xlsx."})
                return

            risk, action, reason = classify_pseint(inputs)
            reference = find_matching_fact(inputs)
            if reference:
                reference["sameRisk"] = comparable(risk) == comparable(reference["risk"])
                reference["sameAction"] = comparable(action) == comparable(reference["action"])
            self.send_json(200, {
                "risk": risk,
                "action": action,
                "reason": reason,
                "databaseReference": reference,
            })
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self.send_json(400, {"error": str(exc)})
        except RuntimeError as exc:
            self.send_json(503, {"error": str(exc)})
        except psycopg.Error:
            self.send_json(503, {"error": "No se pudo consultar Neon. Revisa la conexión de la base de datos."})

    def send_json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)
