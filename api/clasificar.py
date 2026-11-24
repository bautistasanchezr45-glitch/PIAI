from __future__ import annotations

import json
import unicodedata
from http.server import BaseHTTPRequestHandler

import psycopg

from neon_storage import find_matching_fact, get_database_status, get_historical_prediction


MAX_BODY_BYTES = 16_000
OPTIONS = {
    "temperature": {"Correcta", "Fuera de especificación"},
    "pressure": {"Correcta", "Incorrecta"},
    "time": {"Adecuado", "Inadecuado"},
    "rawMaterial": {"Conforme", "No conforme"},
    "machineSettings": {"Correctos", "Incorrectos"},
}
ARCHITECTURES = {"reactive", "model", "objectives", "learning", "hybrid"}
RISK_LEVEL = {"Indefinida": 0, "Bajo": 1, "Medio": 2, "Alto": 3, "Muy alto": 4}


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


def choose_objective_route(risk: str, inputs: dict[str, str], prediction: dict | None) -> tuple[dict, str]:
    basis = risk
    if basis == "Indefinida" and prediction:
        basis = prediction["risk"]
    options = {
        "Bajo": [("Continuar producción", 86, 0), ("Ajustar parámetros", 88, 12)],
        "Medio": [("Ajustar parámetros", 78, 10), ("Inspeccionar producto", 87, 23)],
        "Alto": [("Inspeccionar producto", 91, 12), ("Retener lote", 95, 25)],
        "Muy alto": (
            [("Retener lote", 100, 20), ("Detener proceso", 100, 35)]
            if inputs["rawMaterial"] == "No conforme"
            else [("Detener proceso", 100, 20), ("Retener lote", 94, 23)]
            if inputs["pressure"] == "Incorrecta" and inputs["machineSettings"] == "Incorrectos"
            else [("Retener lote", 98, 20), ("Detener proceso", 100, 30)]
        ),
    }
    candidates = options.get(basis)
    if not candidates:
        return {"risk": risk, "action": "Sin determinar"}, "No hay una ruta objetivo aplicable."
    action, protection, cost = max(candidates, key=lambda item: (item[1] - item[2], -item[2]))
    utility = protection - cost
    return {"risk": basis, "action": action}, f"Meta: proteger la calidad con intervención proporcional. Utilidad = protección {protection} − costo {cost} = {utility} puntos."


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
            architecture = inputs.get("architecture", "reactive")
            if architecture not in ARCHITECTURES:
                raise ValueError("Selecciona una arquitectura válida.")
            previous = inputs.get("previousState") if isinstance(inputs.get("previousState"), dict) else None
            inputs = {key: inputs[key] for key in OPTIONS}

            status = get_database_status()
            if not status["loaded"]:
                self.send_json(409, {"error": "Primero carga Base_Hechos.xlsx y Base_Reglas.xlsx."})
                return

            risk, action, reason = classify_pseint(inputs)
            simulation = {"risk": risk, "action": action, "reason": reason}
            prediction = get_historical_prediction(inputs)
            changes = []
            prior_inputs = previous.get("inputs") if previous else None
            if isinstance(prior_inputs, dict):
                field_labels = {
                    "temperature": "Temperatura", "pressure": "Presión", "time": "Tiempo",
                    "rawMaterial": "Materia prima", "machineSettings": "Ajustes de máquina",
                }
                changes = [
                    {"field": field_labels[key], "from": prior_inputs.get(key), "to": value}
                    for key, value in inputs.items() if prior_inputs.get(key) != value
                ]

            decision = dict(simulation)
            decision_source = "Árbol reactivo PSeInt"
            if architecture == "model" and prediction:
                decision = {"risk": prediction["risk"], "action": prediction["action"]}
                decision_source = "Modelo de frecuencias de Base_Hechos"
                if (
                    previous
                    and previous.get("architecture") == "model"
                    and not changes
                    and previous.get("decision")
                ):
                    decision = previous["decision"]
                    decision_source = "Estado anterior conservado por el modelo"
            elif architecture == "objectives":
                decision, decision_source = choose_objective_route(risk, inputs, prediction)
            elif architecture == "learning" and prediction:
                decision = {"risk": prediction["risk"], "action": prediction["action"]}
                decision_source = f"Aprendizaje por frecuencia: {prediction['learnedCount']} caso(s) etiquetado(s) incorporado(s)"
            elif architecture == "hybrid" and prediction:
                if RISK_LEVEL.get(prediction["risk"], 0) > RISK_LEVEL.get(risk, 0):
                    decision = {"risk": prediction["risk"], "action": prediction["action"]}
                    decision_source = "Híbrido: prevalece la señal histórica de mayor riesgo"
                elif RISK_LEVEL.get(prediction["risk"], 0) == RISK_LEVEL.get(risk, 0) and prediction["action"] != action:
                    decision = {"risk": prediction["risk"], "action": prediction["action"]}
                    decision_source = "Híbrido: combina PSeInt con la acción más frecuente en la base"
                else:
                    decision_source = "Híbrido: resultado PSeInt confirmado por la frecuencia histórica"

            reference = find_matching_fact(inputs)
            if reference:
                reference["sameRisk"] = comparable(risk) == comparable(reference["risk"])
                reference["sameAction"] = comparable(action) == comparable(reference["action"])

            trace = [
                {"title": "1 · Entrada recibida", "detail": "; ".join(f"{key}: {value}" for key, value in inputs.items())},
                {
                    "title": "2 · Estado del entorno",
                    "detail": "Primera observación: se inicializa el estado." if prior_inputs is None
                    else ("Sin cambios respecto a la observación anterior." if not changes
                          else "; ".join(f"{change['field']}: {change['from']} → {change['to']}" for change in changes)),
                },
                {"title": "3 · Árbol de decisión PSeInt", "detail": f"Simulación: {risk} · {action}. {reason}"},
                {
                    "title": "4 · Frecuencia histórica", "detail": (
                        f"Predicción: {prediction['risk']} · {prediction['action']} con {prediction['confidencePct']}% "
                        f"en {prediction['sampleCount']} caso(s) cercanos ({prediction['method']}; {prediction['tieBreak']}); "
                        f"incluye {prediction['learnedCount']} caso(s) nuevos etiquetados."
                        if prediction else "No hay hechos para construir una predicción histórica."
                    ),
                },
                {"title": "5 · Arquitectura y decisión", "detail": f"{architecture}: {decision_source}. Resultado: {decision['risk']} · {decision['action']} ."},
                {
                    "title": "6 · Regla asociada al caso histórico",
                    "detail": f"{reference['ruleId']} (prioridad {reference['priority']}): {reference['condition']}"
                    if reference and reference.get("ruleId") else "No hay una coincidencia exacta con una regla; consulta las reglas completas en «Consultar bases».",
                },
            ]
            next_state = {
                "inputs": inputs,
                "architecture": architecture,
                "decision": {"risk": decision["risk"], "action": decision["action"]},
            }
            self.send_json(200, {
                "risk": decision["risk"],
                "action": decision["action"],
                "reason": decision_source,
                "architecture": architecture,
                "simulation": simulation,
                "prediction": prediction,
                "stateChanges": changes,
                "nextState": next_state,
                "trace": trace,
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
