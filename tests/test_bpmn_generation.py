"""Smoke tests für BPMN generator — testen die reale API."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from process_builder import build_process_definition
from generate_bpmn import generate_xml


def test_build_process_definition_basic():
    """Process Builder erzeugt korrekte Grundstruktur aus kompaktem LLM-Input."""
    compact = {
        "name": "Testprozess",
        "roles": ["Kunde", "Sachbearbeiter"],
        "steps": [
            {"label": "Antrag stellen", "type": "start", "role": "Kunde"},
            {"label": "Antrag prüfen", "type": "task", "role": "Sachbearbeiter"},
            {"label": "Entscheiden", "type": "gateway", "gateway_type": "XOR", "role": "Sachbearbeiter"},
            {"label": "Genehmigt", "type": "end", "role": "Kunde"},
            {"label": "Abgelehnt", "type": "end", "role": "Kunde"},
        ],
        "flow": [
            ["Antrag stellen", "Antrag prüfen"],
            ["Antrag prüfen", "Entscheiden"],
            ["Entscheiden", "Genehmigt", "genehmigt"],
            ["Entscheiden", "Abgelehnt", "abgelehnt"],
        ]
    }
    result = build_process_definition(compact)

    assert result["name"] == "Testprozess"
    assert result["id"] == "Process_1"
    assert len(result["lanes"]) == 2
    assert len(result["flows"]) == 4
    # Check lane assignments
    kunden_elements = [e["name"] for lane in result["lanes"] if lane["name"] == "Kunde" for e in lane["elements"]]
    assert "Antrag stellen" in kunden_elements
    assert "Genehmigt" in kunden_elements


def test_generate_xml_produces_valid_bpmn():
    """generate_xml erzeugt gültiges BPMN 2.0 XML."""
    compact = {
        "name": "Minimal",
        "roles": ["Org"],
        "steps": [
            {"label": "Start", "type": "start", "role": "Org"},
            {"label": "Aufgabe", "type": "task", "role": "Org"},
            {"label": "Ende", "type": "end", "role": "Org"},
        ],
        "flow": [
            ["Start", "Aufgabe"],
            ["Aufgabe", "Ende"],
        ]
    }
    process_def = build_process_definition(compact)
    xml_str = generate_xml(process_def)

    assert isinstance(xml_str, str)
    assert '<?xml version="1.0"' in xml_str
    assert "<bpmn:process" in xml_str
    assert '<bpmn:startEvent' in xml_str
    assert '<bpmn:endEvent' in xml_str


def test_build_process_definition_no_roles():
    """Ohne Rollen wird default 'Organisation' verwendet."""
    compact = {
        "name": "Ohne Rollen",
        "steps": [
            {"label": "Start", "type": "start"},
            {"label": "Ende", "type": "end"},
        ],
        "flow": [["Start", "Ende"]]
    }
    result = build_process_definition(compact)
    assert len(result["lanes"]) == 1
    assert result["lanes"][0]["name"] == "Organisation"


def test_build_process_definition_skips_empty_labels():
    """Leere Labels werden ignoriert."""
    compact = {
        "name": "Mit Leeren",
        "steps": [
            {"label": "", "type": "start"},
            {"label": "Task", "type": "task"},
        ],
        "flow": []
    }
    result = build_process_definition(compact)
    elements = [e["name"] for lane in result["lanes"] for e in lane["elements"]]
    assert "" not in elements


@pytest.mark.parametrize("gateway_type", ["XOR", "PARALLEL"])
def test_gateway_types(gateway_type):
    """Verschiedene Gateway-Typen werden korrekt verarbeitet."""
    compact = {
        "name": "Gateway Test",
        "steps": [
            {"label": "Start", "type": "start"},
            {"label": "Gate", "type": "gateway", "gateway_type": gateway_type},
            {"label": "A", "type": "task"},
            {"label": "B", "type": "task"},
        ],
        "flow": [
            ["Start", "Gate"],
            ["Gate", "A"],
            ["Gate", "B"],
        ]
    }
    process_def = build_process_definition(compact)
    xml_str = generate_xml(process_def)
    assert xml_str is not None
    # Gateway-Tag vorhanden
    expected_tag = "exclusiveGateway" if gateway_type == "XOR" else "parallelGateway"
    assert f"<bpmn:{expected_tag}" in xml_str
