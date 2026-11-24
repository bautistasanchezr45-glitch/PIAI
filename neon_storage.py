"""Neon/PostgreSQL persistence for Vercel API functions."""

from __future__ import annotations

import os
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
    if not row:
        return {"loaded": False}
    return {
        "loaded": True,
        "facts": row[0],
        "rules": row[1],
        "importedAt": row[2].isoformat(),
    }
