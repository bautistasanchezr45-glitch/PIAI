from __future__ import annotations

import io
import posixpath
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET

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
        raise ValueError("Una celda del Excel no tiene una referencia vÃ¡lida.")
    index = 0
    for char in letters.group(0).upper():
        index = index * 26 + ord(char) - ord("A") + 1
    return index - 1


def read_xlsx(data: bytes, label: str) -> list[list[str]]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError(f"{label}: el archivo no es un libro .xlsx vÃ¡lido.") from exc

    with archive:
        names = set(archive.namelist())
        if "xl/workbook.xml" not in names or "xl/_rels/workbook.xml.rels" not in names:
            raise ValueError(f"{label}: no se encontrÃ³ la estructura de un libro Excel.")
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
                raise ValueError(f"{label}: no se encontrÃ³ la primera hoja del libro.")

            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in names:
                shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                shared_strings = [
                    "".join(node.text or "" for node in item.findall(".//main:t", NS))
                    for item in shared_root.findall("main:si", NS)
                ]
            sheet = ET.fromstring(archive.read(sheet_path))
        except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
            raise ValueError(f"{label}: el libro estÃ¡ daÃ±ado o tiene una estructura no compatible.") from exc

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
                        raise ValueError(f"{label}: una celda usa una referencia de texto invÃ¡lida.") from exc
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
            raise ValueError(f"{filename}, fila {row_number}: el identificador {identifier} estÃ¡ duplicado.")
        seen.add(identifier)
        records.append(record)
    if not records:
        raise ValueError(f"{filename}: no se encontraron registros para importar.")
    return records


