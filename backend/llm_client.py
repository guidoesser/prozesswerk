# Copyright (c) 2026 Guido Esser
# Licensed under the Elastic License 2.0 — see LICENSE file for details.
# Community Edition — self-hosting free. SaaS/Managed Service requires commercial license.

import os
import json
import re
from openai import OpenAI
try:
    from . import process_builder
except ImportError:
    import process_builder

# Env vars:
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")

BPMN_SYSTEM_PROMPT = """Du bist der "BPMN"-Assistent. Extrahiere aus der Prozessbeschreibung ein kompaktes JSON.

Extrahiere: Rollen, Schritte (als Verb+Objekt), Entscheidungen mit Ja/Nein-Bedingungen, Ausnahmen, Start/Ende.

KOMPAKTES JSON-FORMAT (spart Tokens — KEINE IDs, KEINE detaillierten Elementstrukturen):
{
  "name": "Prozessname",
  "roles": ["Kunde", "Sachbearbeiter", "System"],
  "steps": [
    {"role": "Kunde", "label": "Bestellung aufgeben", "type": "start"},
    {"role": "System", "label": "Verf\u00fcgbarkeit pr\u00fcfen", "type": "task"},
    {"role": "System", "label": "Verf\u00fcgbar?", "type": "gateway"},
    {"role": "System", "label": "Bestellung ausf\u00fchren", "type": "task"},
    {"role": "Kunde", "label": "Bestellung erhalten", "type": "end"}
  ],
  "flow": [
    ["Bestellung aufgeben", "Verf\u00fcgbarkeit pr\u00fcfen"],
    ["Verf\u00fcgbarkeit pr\u00fcfen", "Verf\u00fcgbar?"],
    ["Verf\u00fcgbar?", "Bestellung ausf\u00fchren", "Ja"],
    ["Verf\u00fcgbar?", "Bestellung erhalten", "Nein"]
  ],
  "assumptions": ["Annahme 1"],
  "open_questions": ["Frage 1?"],
  "improvements": ["Vorschlag 1"]
}

REGELN (Camunda Modeling Styles — https://camunda.com/bpmn/examples/):
- BENENNUNG (streng):
  - Events: Objekt + Partizip II ("Bestellung aufgegeben", "Antrag abgelehnt")
  - Tasks: Objekt + Verb im Infinitiv ("Antrag pr\u00fcfen", "Zahlung ausf\u00fchren")
  - Gateways: Frage mit Fragezeichen ("Vollst\u00e4ndig?", "Genehmigt?")
  - Sequence Flows (Bedingungen): Kurze Antwort ("Ja", "Nein", "Nachbesserung n\u00f6tig")
- SYMMETRIE: Gateway-Zweige m\u00f6glichst symmetrisch aufbauen \u2014 beide Pfade
  sollten \u00e4hnlich viele Schritte haben (kein "Ja=1 Schritt, Nein=15 Schritte")
- KEINE KREUZENDEN FLOWS: Elemente-Reihenfolge so w\u00e4hlen, dass Flows
  sich m\u00f6glichst nicht kreuzen. Oberer Pfad = obere Lane, usw.
- type: start | end | task | gateway
- flow-Array: [Von-Label, Nach-Label, optional Bedingung]
- Ausnahmen: eigener Pfad zu end-Label
- Rollen-Reihenfolge = Lane-Reihenfolge (oben \u2192 unten)
- NUR JSON ausgeben, KEINEN Text, KEINE Codebl\u00f6cke
- Bei wenig Input: generischen Ablauf liefern"""

ITERATION_PROMPT_SUFFIX = """

ITERATION-MODUS: Ein bestehender Prozess wird verfeinert.
- Alle unveranderten Elemente MUSSEN exakt gleiche Label und role behalten.
- Nur die vom Nutzer gewunschten Anderungen umsetzen.
- Keine zusatzlichen Elemente oder Umbenennungen ohne expliziten Auftrag.
- Die Reihenfolge der Steps soll moglichst erhalten bleiben."""


def generate_bpmn_from_text(user_input: str, existing_definition: dict = None):
    """Send text to LLM, expand compact response into full process definition.
    
    If existing_definition is provided (iteration), preserve IDs of unchanged elements."""
    if not LLM_API_KEY:
        raise LLMNotConfiguredError("LLM_API_KEY is not configured. Set it in .env")

    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

    # Build user message with optional existing definition context
    user_message = user_input
    system_prompt = BPMN_SYSTEM_PROMPT
    if existing_definition:
        existing_json = json.dumps(existing_definition, ensure_ascii=False, indent=2)
        user_message = (
            f"Bestehender Prozess (IDs MÜSSEN für unveränderte Elemente erhalten bleiben):\n\n"
            f"{existing_json}\n\n"
            f"Änderungswunsch: {user_input}"
        )
        system_prompt += ITERATION_PROMPT_SUFFIX

    # Try with 4096 tokens first, retry with 8192 if truncated
    for attempt, max_tok in enumerate([4096, 8192]):
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.1,
            max_tokens=max_tok,
        )

        content = response.choices[0].message.content
        finish_reason = response.choices[0].finish_reason

        # Parse JSON — try multiple strategies
        compact = None
        try:
            compact = json.loads(content)
        except json.JSONDecodeError:
            pass

        if compact is None:
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
            if json_match:
                try:
                    compact = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass

        if compact is None:
            start = content.find('{')
            end = content.rfind('}')
            if start >= 0 and end > start:
                try:
                    compact = json.loads(content[start:end+1])
                except json.JSONDecodeError:
                    pass

        if compact is not None:
            break  # Success

        if finish_reason != "length":
            # Not truncated, just malformed — don't retry
            raise ValueError(f"LLM response was not valid JSON: {content[:500]}")

        # Truncated — will retry with 8192
        if attempt == 0:
            continue

    if compact is None:
        snippet = content[:500]
        raise ValueError(f"LLM response was not valid JSON (Antwort wurde abgeschnitten): {snippet}")

    # Expand compact format -> full process_definition
    process_def = process_builder.build_process_definition(compact, existing=existing_definition)

    result = {
        "process_definition": process_def,
        "notes": {
            "assumptions": compact.get("assumptions", []),
            "open_questions": compact.get("open_questions", []),
            "improvements": compact.get("improvements", []),
        }
    }

    return result


class LLMNotConfiguredError(Exception):
    pass


def is_configured() -> bool:
    return bool(LLM_API_KEY)
