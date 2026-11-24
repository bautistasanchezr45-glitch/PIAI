"""Neon/PostgreSQL persistence for Vercel API functions."""

from __future__ import annotations

import os
import uuid
import psycopg


def connect_database():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("Falta configurar DATABASE_URL en las variables de Vercel.")
    return psycopg.connect(database_url, connect_timeout=10)


def ensure_schema(connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS reglas (
            id_regla TEXT PRIMARY KEY,
            condicion TEXT NOT NULL,
            resultado TEXT NOT NULL,
            prioridad INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS hechos (
            id_hecho TEXT PRIMARY KEY,
            temperatura TEXT NOT NULL,
            presion TEXT NOT NULL,
            tiempo TEXT NOT NULL,
            materia_prima TEXT NOT NULL,
            ajustes_maquina TEXT NOT NULL,
            regla_aplicable TEXT NOT NULL,
            riesgo_esperado TEXT NOT NULL,
            accion_esperada TEXT NOT NULL,
            tipo_dato TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS importacion (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            archivo_hechos TEXT NOT NULL,
            archivo_reglas TEXT NOT NULL,
            cantidad_hechos INTEGER NOT NULL,
            cantidad_reglas INTEGER NOT NULL,
            cargado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS casos_aprendidos (
            id_caso TEXT PRIMARY KEY,
            temperatura TEXT NOT NULL,
            presion TEXT NOT NULL,
            tiempo TEXT NOT NULL,
            materia_prima TEXT NOT NULL,
            ajustes_maquina TEXT NOT NULL,
            riesgo_observado TEXT NOT NULL,
            accion_observada TEXT NOT NULL,
            creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def import_into_database(facts, rules, facts_name: str, rules_name: str) -> None:
    valid_rule_ids = {item["id_regla"] for item in rules}
    missing_rules = sorted({item["regla_aplicable"] for item in facts} - valid_rule_ids)
    if missing_rules:
        raise ValueError("Hay hechos que apuntan a reglas inexistentes: " + ", ".join(missing_rules[:10]) + ".")

    with connect_database() as connection:
        ensure_schema(connection)
        connection.execute("DELETE FROM hechos")
        connection.execute("DELETE FROM reglas")
        with connection.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO reglas (id_regla, condicion, resultado, prioridad) VALUES (%s, %s, %s, %s)",
                [
                    (r["id_regla"], r["condicion_si"], r["accion_resultado_entonces"], int(float(r["prioridad"])))
                    for r in rules
                ],
            )
            cursor.executemany(
                """INSERT INTO hechos (
                    id_hecho, temperatura, presion, tiempo, materia_prima, ajustes_maquina,
                    regla_aplicable, riesgo_esperado, accion_esperada, tipo_dato
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    (
                        f["id_hecho"], f["f1_temperatura"], f["f2_presion"], f["f3_tiempo"],
                        f["f4_materia_prima"], f["f5_ajustes_maquina"], f["regla_aplicable"],
                        f["riesgo_esperado"], f["accion_esperada"], f["tipo_dato"],
                    )
                    for f in facts
                ],
            )
        connection.execute(
            """INSERT INTO importacion (id, archivo_hechos, archivo_reglas, cantidad_hechos, cantidad_reglas)
               VALUES (1, %s, %s, %s, %s)
               ON CONFLICT (id) DO UPDATE SET archivo_hechos=EXCLUDED.archivo_hechos,
                 archivo_reglas=EXCLUDED.archivo_reglas, cantidad_hechos=EXCLUDED.cantidad_hechos,
                 cantidad_reglas=EXCLUDED.cantidad_reglas, cargado_en=CURRENT_TIMESTAMP""",
            (facts_name, rules_name, len(facts), len(rules)),
        )


def get_database_status() -> dict:
    with connect_database() as connection:
        ensure_schema(connection)
        row = connection.execute(
            "SELECT cantidad_hechos, cantidad_reglas, cargado_en FROM importacion WHERE id=1"
        ).fetchone()
        learned = connection.execute("SELECT COUNT(*) FROM casos_aprendidos").fetchone()[0]
    if not row:
        return {"loaded": False}
    return {
        "loaded": True,
        "facts": row[0],
        "rules": row[1],
        "learned": learned,
        "importedAt": row[2].isoformat(),
    }


def find_matching_fact(inputs: dict[str, str]) -> dict | None:
    with connect_database() as connection:
        count = connection.execute(
            """SELECT COUNT(*) FROM hechos WHERE temperatura=%s AND presion=%s AND tiempo=%s
               AND materia_prima=%s AND ajustes_maquina=%s""",
            (inputs["temperature"], inputs["pressure"], inputs["time"], inputs["rawMaterial"], inputs["machineSettings"]),
        ).fetchone()[0]
        row = connection.execute(
            """SELECT f.id_hecho, f.riesgo_esperado, f.accion_esperada, f.regla_aplicable,
                      f.tipo_dato, r.condicion, r.resultado, r.prioridad
               FROM hechos f LEFT JOIN reglas r ON r.id_regla=f.regla_aplicable
               WHERE f.temperatura=%s AND f.presion=%s AND f.tiempo=%s
                 AND f.materia_prima=%s AND f.ajustes_maquina=%s
               ORDER BY CASE WHEN LOWER(f.tipo_dato)='real' THEN 0 ELSE 1 END, f.id_hecho
               LIMIT 1""",
            (inputs["temperature"], inputs["pressure"], inputs["time"], inputs["rawMaterial"], inputs["machineSettings"]),
        ).fetchone()
    if not row:
        return None
    return {
        "examples": count,
        "factId": row[0],
        "risk": row[1],
        "action": row[2],
        "ruleId": row[3],
        "type": row[4],
        "condition": row[5],
        "ruleResult": row[6],
        "priority": row[7],
    }


def get_historical_prediction(inputs: dict[str, str]) -> dict | None:
    keys = ["temperature", "pressure", "time", "rawMaterial", "machineSettings"]
    severity = {"Bajo": 1, "Medio": 2, "Alto": 3, "Muy alto": 4}
    with connect_database() as connection:
        rows = connection.execute(
            """SELECT id_hecho, temperatura, presion, tiempo, materia_prima, ajustes_maquina,
                      regla_aplicable, riesgo_esperado, accion_esperada, tipo_dato
               FROM hechos
               UNION ALL
               SELECT id_caso, temperatura, presion, tiempo, materia_prima, ajustes_maquina,
                      'APRENDIDO', riesgo_observado, accion_observada, 'Aprendido'
               FROM casos_aprendidos"""
        ).fetchall()
        if not rows:
            return None

        distances = [sum(row[index + 1] != inputs[key] for index, key in enumerate(keys)) for row in rows]
        closest_distance = min(distances)
        nearest = [row for row, distance in zip(rows, distances) if distance == closest_distance]
        grouped: dict[tuple[str, str], list[tuple]] = {}
        for row in nearest:
            grouped.setdefault((row[7], row[8]), []).append(row)
        ranked = sorted(
            grouped.items(),
            key=lambda item: (len(item[1]), severity.get(item[0][0], 0)),
            reverse=True,
        )
        (predicted_risk, predicted_action), predicted_rows = ranked[0]
        total = len(nearest)
        learned_count = sum(row[9] == "Aprendido" for row in nearest)
        distribution = [
            {"risk": risk, "action": action, "count": len(group), "percent": round(len(group) * 100 / total, 1)}
            for (risk, action), group in ranked
        ]
        chosen_rules: dict[str, list[tuple]] = {}
        for row in predicted_rows:
            chosen_rules.setdefault(row[6], []).append(row)
        rule_id, rule_rows = max(chosen_rules.items(), key=lambda item: len(item[1]))
        rule = connection.execute(
            "SELECT condicion, resultado, prioridad FROM reglas WHERE id_regla=%s",
            (rule_id,),
        ).fetchone()

    return {
        "risk": predicted_risk,
        "action": predicted_action,
        "sampleCount": total,
        "learnedCount": learned_count,
        "distance": closest_distance,
        "confidencePct": round(len(predicted_rows) * 100 / total, 1),
        "tieBreak": "En empate se elige el riesgo de mayor severidad.",
        "method": "frecuencia de coincidencia exacta" if closest_distance == 0 else "frecuencia de casos más cercanos",
        "factIds": [row[0] for row in nearest[:5]],
        "ruleId": rule_id,
        "ruleCondition": rule[0] if rule else None,
        "ruleResult": rule[1] if rule else None,
        "rulePriority": rule[2] if rule else None,
        "distribution": distribution,
    }


def get_knowledge_base() -> dict:
    with connect_database() as connection:
        facts = connection.execute(
            """SELECT id_hecho, temperatura, presion, tiempo, materia_prima, ajustes_maquina,
                      regla_aplicable, riesgo_esperado, accion_esperada, tipo_dato
               FROM hechos
               UNION ALL
               SELECT id_caso, temperatura, presion, tiempo, materia_prima, ajustes_maquina,
                      'APRENDIDO', riesgo_observado, accion_observada, 'Aprendido'
               FROM casos_aprendidos
               ORDER BY 1"""
        ).fetchall()
        rules = connection.execute(
            "SELECT id_regla, condicion, resultado, prioridad FROM reglas ORDER BY prioridad, id_regla"
        ).fetchall()
    return {
        "facts": [
            {"id": r[0], "temperature": r[1], "pressure": r[2], "time": r[3], "rawMaterial": r[4],
             "machineSettings": r[5], "ruleId": r[6], "risk": r[7], "action": r[8], "type": r[9]}
            for r in facts
        ],
        "rules": [
            {"id": r[0], "condition": r[1], "result": r[2], "priority": r[3]}
            for r in rules
        ],
    }


def save_learning_case(inputs: dict[str, str], risk: str, action: str) -> str:
    case_id = "AP-" + uuid.uuid4().hex[:12].upper()
    with connect_database() as connection:
        ensure_schema(connection)
        connection.execute(
            """INSERT INTO casos_aprendidos (
                   id_caso, temperatura, presion, tiempo, materia_prima, ajustes_maquina,
                   riesgo_observado, accion_observada
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (case_id, inputs["temperature"], inputs["pressure"], inputs["time"],
             inputs["rawMaterial"], inputs["machineSettings"], risk, action),
        )
    return case_id
