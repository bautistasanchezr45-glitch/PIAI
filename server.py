from __future__ import annotations

import io
import json
import posixpath
import re
import sqlite3
import unicodedata
import zipfile
from email.parser import BytesParser
from email.policy import default
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "control_calidad.db"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
EXPECTED = {
    "facts": [
        "id_hecho", "f1_temperatura", "f2_presion", "f3_tiempo",
        "f4_materia_prima", "f5_ajustes_maquina", "regla_aplicable",
        "riesgo_esperado", "accion_esperada", "tipo_dato",
    ],
    "rules": ["id_regla", "condicion_si", "accion_resultado_entonces", "prioridad"],
}


def normalize_header(value: str) -> str:
    plain = "".join(ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "_", plain.lower()).strip("_")


def column_index(cell_ref: str) -> int:
    letters = re.match(r"[A-Za-z]+", cell_ref)
    if not letters:
        raise ValueError("Una celda del Excel no tiene una referencia válida.")
    index = 0
    for char in letters.group(0).upper():
        index = index * 26 + ord(char) - ord("A") + 1
    return index - 1


def read_xlsx(data: bytes, label: str) -> list[list[str]]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError(f"{label}: el archivo no es un libro .xlsx válido.") from exc

    with archive:
        names = set(archive.namelist())
        if "xl/workbook.xml" not in names or "xl/_rels/workbook.xml.rels" not in names:
            raise ValueError(f"{label}: no se encontró la estructura de un libro Excel.")
        try:
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            rels_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            relations = {item.attrib["Id"]: item.attrib["Target"] for item in rels_root}
            sheets = workbook.findall("main:sheets/main:sheet", NS)
            if not sheets:
                raise ValueError(f"{label}: el libro no contiene hojas.")
            sheet_rel = sheets[0].attrib[f"{{{NS['rel']}}}id"]
            target = relations[sheet_rel]
            sheet_path = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
            if sheet_path not in names:
                raise ValueError(f"{label}: no se encontró la primera hoja del libro.")

            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in names:
                shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                shared_strings = [
                    "".join(node.text or "" for node in item.findall(".//main:t", NS))
                    for item in shared_root.findall("main:si", NS)
                ]
            sheet = ET.fromstring(archive.read(sheet_path))
        except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
            raise ValueError(f"{label}: el libro está dañado o tiene una estructura no compatible.") from exc

        rows: list[list[str]] = []
        for row in sheet.findall(".//main:sheetData/main:row", NS):
            values: dict[int, str] = {}
            for cell in row.findall("main:c", NS):
                ref = cell.attrib.get("r", "")
                index = column_index(ref)
                cell_type = cell.attrib.get("t")
                value_node = cell.find("main:v", NS)
                value = value_node.text or "" if value_node is not None else ""
                if cell_type == "s" and value:
                    try:
                        value = shared_strings[int(value)]
                    except (ValueError, IndexError) as exc:
                        raise ValueError(f"{label}: una celda usa una referencia de texto inválida.") from exc
                elif cell_type == "inlineStr":
                    value = "".join(node.text or "" for node in cell.findall(".//main:t", NS))
                values[index] = value.strip()
            if values and any(values.values()):
                row_width = max(values) + 1
                rows.append([values.get(index, "") for index in range(row_width)])
        if len(rows) < 2:
            raise ValueError(f"{label}: se requiere una fila de encabezados y al menos un registro.")
        return rows


def parse_workbook(data: bytes, kind: str, filename: str) -> list[dict[str, str]]:
    rows = read_xlsx(data, filename)
    headers = [normalize_header(value) for value in rows[0]]
    expected = EXPECTED[kind]
    if headers[: len(expected)] != expected:
        pretty = ", ".join(expected)
        raise ValueError(f"{filename}: los encabezados no coinciden. Se esperaban: {pretty}.")

    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for row_number, values in enumerate(rows[1:], start=2):
        values = (values + [""] * len(expected))[: len(expected)]
        if not any(value.strip() for value in values):
            continue
        if len(values) < len(expected) or any(not value.strip() for value in values):
            missing = [expected[i] for i, value in enumerate(values) if not value.strip()]
            raise ValueError(f"{filename}, fila {row_number}: faltan valores en {', '.join(missing)}.")
        record = dict(zip(expected, values))
        identifier = record[expected[0]]
        if identifier in seen:
            raise ValueError(f"{filename}, fila {row_number}: el identificador {identifier} está duplicado.")
        seen.add(identifier)
        records.append(record)
    if not records:
        raise ValueError(f"{filename}: no se encontraron registros para importar.")
    return records


def connect_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS reglas (
            id_regla TEXT PRIMARY KEY,
            condicion TEXT NOT NULL,
            resultado TEXT NOT NULL,
            prioridad INTEGER NOT NULL
        );
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
        );
        CREATE TABLE IF NOT EXISTS importacion (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            archivo_hechos TEXT NOT NULL,
            archivo_reglas TEXT NOT NULL,
            cantidad_hechos INTEGER NOT NULL,
            cantidad_reglas INTEGER NOT NULL,
            cargado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    return connection


def import_into_database(facts: list[dict[str, str]], rules: list[dict[str, str]], facts_name: str, rules_name: str) -> None:
    valid_rule_ids = {item["id_regla"] for item in rules}
    missing_rules = sorted({item["regla_aplicable"] for item in facts} - valid_rule_ids)
    if missing_rules:
        raise ValueError("Hay hechos que apuntan a reglas inexistentes: " + ", ".join(missing_rules[:10]) + ".")

    connection = connect_db()
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM hechos")
        connection.execute("DELETE FROM reglas")
        connection.executemany(
            "INSERT INTO reglas (id_regla, condicion, resultado, prioridad) VALUES (?, ?, ?, ?)",
            [(r["id_regla"], r["condicion_si"], r["accion_resultado_entonces"], int(float(r["prioridad"]))) for r in rules],
        )
        connection.executemany(
            """INSERT INTO hechos (
                id_hecho, temperatura, presion, tiempo, materia_prima, ajustes_maquina,
                regla_aplicable, riesgo_esperado, accion_esperada, tipo_dato
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
            """INSERT INTO importacion (id, archivo_hechos, archivo_reglas, cantidad_hechos, cantidad_reglas, cargado_en)
               VALUES (1, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(id) DO UPDATE SET archivo_hechos=excluded.archivo_hechos,
                 archivo_reglas=excluded.archivo_reglas, cantidad_hechos=excluded.cantidad_hechos,
                 cantidad_reglas=excluded.cantidad_reglas, cargado_en=CURRENT_TIMESTAMP""",
            (facts_name, rules_name, len(facts), len(rules)),
        )
        connection.commit()
    except (ValueError, sqlite3.Error):
        connection.rollback()
        raise
    finally:
        connection.close()


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/api/status":
            self.send_json(200, self.database_status())
            return
        path = unquote(urlparse(self.path).path)
        if path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/importar":
            self.send_json(404, {"error": "Ruta no encontrada."})
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_UPLOAD_BYTES:
            self.send_json(413, {"errors": ["La carga está vacía o supera el límite de 20 MB."]})
            return
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("multipart/form-data"):
            self.send_json(400, {"errors": ["Envía ambos Excel usando el formulario de carga."]})
            return

        try:
            body = self.rfile.read(length)
            mime_message = BytesParser(policy=default).parsebytes(
                b"Content-Type: " + content_type.encode("ascii") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
            )
            uploads = {}
            for part in mime_message.iter_parts():
                field = part.get_param("name", header="content-disposition")
                filename = Path(part.get_filename() or "").name
                payload = part.get_payload(decode=True) or b""
                if field in {"facts", "rules"} and filename:
                    if len(payload) > MAX_UPLOAD_BYTES:
                        raise ValueError(f"{filename}: supera el límite de 20 MB.")
                    uploads[field] = (filename, payload)
            if "facts" not in uploads or "rules" not in uploads:
                raise ValueError("Selecciona tanto Base_Hechos.xlsx como Base_Reglas.xlsx.")
            facts_name, facts_data = uploads["facts"]
            rules_name, rules_data = uploads["rules"]
            if not facts_name.lower().endswith(".xlsx") or not rules_name.lower().endswith(".xlsx"):
                raise ValueError("Los dos archivos deben estar en formato .xlsx.")
            facts = parse_workbook(facts_data, "facts", facts_name)
            rules = parse_workbook(rules_data, "rules", rules_name)
            import_into_database(facts, rules, facts_name, rules_name)
            self.send_json(200, {"ok": True, "facts": len(facts), "rules": len(rules)})
        except (ValueError, sqlite3.Error) as exc:
            self.send_json(400, {"errors": [str(exc)]})
        except Exception:
            self.send_json(400, {"errors": ["No se pudo leer el contenido de los archivos. Verifica que sean libros .xlsx válidos."]})

    def database_status(self) -> dict:
        if not DB_PATH.exists():
            return {"loaded": False}
        try:
            with sqlite3.connect(DB_PATH) as connection:
                row = connection.execute("SELECT cantidad_hechos, cantidad_reglas, cargado_en FROM importacion WHERE id=1").fetchone()
            return {"loaded": bool(row), "facts": row[0], "rules": row[1], "importedAt": row[2]} if row else {"loaded": False}
        except sqlite3.Error:
            return {"loaded": False}

    def send_json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)


if __name__ == "__main__":
    address = ("127.0.0.1", 8000)
    print("Control de Calidad disponible en http://127.0.0.1:8000")
    print("Presiona Ctrl+C para detener el servidor.")
    try:
        ThreadingHTTPServer(address, AppHandler).serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
