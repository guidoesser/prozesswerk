# Copyright (c) 2026 Guido Esser
# Licensed under the MIT License — see LICENSE file for details.
"""Diagramm-Speicher (SQLite) für Prozesswerk — Mehr-Diagramm-Projekt.

Verwaltet gespeicherte Diagramme (BPMN-XML + Prozess-Definition) und vergibt
bei jedem Speichern eine EINDEUTIGE Prozess-ID, damit Call Activities
per ``calledElement`` auf andere Diagramme verweisen können.
"""

import json
import os
import re
import sqlite3
import time

DATA_DIR = os.getenv(
    "DATA_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"),
)
DB_PATH = os.path.join(DATA_DIR, "prozesswerk.db")


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS diagrams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            process_id TEXT NOT NULL,
            bpmn_xml TEXT NOT NULL,
            process_definition TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def _row_to_diagram(row, include_body=True):
    d = {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "process_id": row["process_id"],
        "updated_at": row["updated_at"],
    }
    if include_body:
        d["bpmn_xml"] = row["bpmn_xml"]
        try:
            d["process_definition"] = json.loads(row["process_definition"] or "{}")
        except json.JSONDecodeError:
            d["process_definition"] = {}
    return d


def list_diagrams():
    conn = _conn()
    rows = conn.execute(
        "SELECT id, name, description, process_id, updated_at "
        "FROM diagrams ORDER BY updated_at DESC, id DESC"
    ).fetchall()
    conn.close()
    return [_row_to_diagram(r, include_body=False) for r in rows]


def get_diagram(diagram_id):
    conn = _conn()
    row = conn.execute("SELECT * FROM diagrams WHERE id = ?", (diagram_id,)).fetchone()
    conn.close()
    return _row_to_diagram(row) if row else None


def _unique_process_id(name):
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") or "Prozess"
    base = f"Process_{slug}"
    conn = _conn()
    candidate, i = base, 2
    while conn.execute("SELECT 1 FROM diagrams WHERE process_id = ?", (candidate,)).fetchone():
        candidate = f"{base}_{i}"
        i += 1
    conn.close()
    return candidate


def create_diagram(name, process_id, bpmn_xml, process_definition=None, description=""):
    """Speichert ein Diagramm. Vergibt eine eindeutige Prozess-ID und schreibt
    sie in XML + Prozess-Definition zurück."""
    new_pid = _unique_process_id(name)
    xml = bpmn_xml or ""
    if process_id and process_id != new_pid:
        xml = xml.replace(process_id, new_pid)

    pdef = dict(process_definition) if isinstance(process_definition, dict) else {}
    pdef["id"] = new_pid

    now = _now()
    conn = _conn()
    cur = conn.execute(
        "INSERT INTO diagrams (name, description, process_id, bpmn_xml, process_definition, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, description, new_pid, xml, json.dumps(pdef, ensure_ascii=False), now, now),
    )
    conn.commit()
    diagram_id = cur.lastrowid
    conn.close()
    return get_diagram(diagram_id)


def rename_diagram(diagram_id, name):
    conn = _conn()
    conn.execute(
        "UPDATE diagrams SET name = ?, updated_at = ? WHERE id = ?",
        (name, _now(), diagram_id),
    )
    conn.commit()
    conn.close()
    return get_diagram(diagram_id)


def delete_diagram(diagram_id):
    conn = _conn()
    conn.execute("DELETE FROM diagrams WHERE id = ?", (diagram_id,))
    conn.commit()
    conn.close()
