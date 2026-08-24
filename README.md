# Prozesswerk

**Textbasierte Geschäftsprozess-Modellierung – natürlichsprachlich → BPMN 2.0 Diagramm**

Gib einen Prozess in natürlicher Sprache ein (per Text oder Sprache), und die App erzeugt daraus ein vollständiges BPMN 2.0 Diagramm als importierbares BPMN-XML mit automatischem Layout. Das Ergebnis kann direkt im integrierten bpmn-js Editor visualisiert und nachbearbeitet werden.

🛡️ **Selfhosted = maximaler Datenschutz** — deine Prozessbeschreibungen verlassen deinen Server nie. 🔌 **Beliebige KI einbindbar** — OpenAI, DeepSeek, Anthropic, Ollama, lokale LLMs: jeder OpenAI-kompatible API-Endpunkt funktioniert.

---

## Features

- 🎤 **Spracheingabe** – Diktiere Prozesse via Mikrofon (Web Speech API)
- 🎤 **Prozess-Interview** – 6-Schritt-Wizard führt strukturiert durch die Prozessbeschreibung (Auslöser → Rollen → Ablauf → Entscheidungen → Ausnahmen → Abschluss)
- 🤖 **LLM-gestützt** – Nutzt frei wählbare KI zur Extraktion von Rollen, Schritten, Entscheidungen und Ausnahmen (Camunda Modeling Styles)
- 🔌 **Beliebige LLMs** – OpenAI, DeepSeek, Anthropic, Ollama, lokale Modelle – jeder OpenAI-kompatible Endpunkt
- 🛡️ **Selfhosted** – Alle Daten bleiben auf deinem Server, keine Cloud-Abhängigkeit
- 📄 **BPMN 2.0 XML** – Vollständig mit DI-Layout (ELK.js Sugiyama + Spine-Gap-Routing) – importierbar in Camunda, bpmn.io, Signavio uvm.
- ✏️ **bpmn-js Editor** – Generiertes BPMN visuell im Browser öffnen und nachbearbeiten
- 🔄 **Iterativ** – Verfeinere das Diagramm durch weitere Angaben (Prozesskontext wird mitgeschickt)
- 📋 **Beispiele** – 5 Best-Practice-Vorlagen (Dropdown)
- 🐳 **Docker** – Einfach starten mit `docker compose up`

---

## Quick Start

### 1. Voraussetzungen

- Docker & Docker Compose
- Ein OpenAI-kompatibler API-Key (OpenAI, OpenRouter, Anthropic, Deepseek, lokaler LLM, …)

### 2. Starten

```bash
# Repository klonen
git clone https://github.com/guidoesser/prozesswerk.git
cd prozesswerk

# API-Key konfigurieren
cp .env.example .env
# → .env öffnen und LLM_API_KEY eintragen

# Starten
docker compose up -d
```

👉 **App öffnen:** [http://localhost:8000](http://localhost:8000)

### 3. Nutzung

**Freitext (Generator):**
1. Prozess in das Textfeld eingeben (oder auf Mikrofon tippen und sprechen)
2. „Generieren" klicken
3. BPMN XML + Notizen + Prozessstruktur in Tabs anschauen
4. „✏️ In Editor öffnen" für visuelles BPMN-Diagramm
5. Bei Bedarf: Verbesserungswunsch eingeben und Diagramm verfeinern
6. BPMN-XML herunterladen

**Geführt (Interview):**
1. „🎤 Prozess-Interview" klicken
2. 6 Fragen durchgehen – Auslöser, Rollen, Ablauf, Entscheidungen, Ausnahmen, Abschluss
3. Generierte Prozessbeschreibung wird automatisch in den Generator übernommen

## Beispiel-Eingabe

> „Ein Kunde gibt eine Bestellung auf. Das System prüft die Verfügbarkeit der Artikel. Wenn alle Artikel verfügbar sind, wird die Bestellung an den Versand weitergeleitet. Wenn nicht, erhält der Kunde eine Benachrichtigung über nicht verfügbare Artikel."

→ **Daraus wird** ein BPMN-Diagramm mit:
- **Lanes:** Kunde, System, Versand
- **Gateway:** Verfügbar? (XOR)
- **Tasks:** Bestellung aufgeben, Verfügbarkeit prüfen, Bestellung versenden, Benachrichtigung senden
- **Fehlerpfad:** Nicht verfügbare Artikel → Benachrichtigung

## Konfiguration

| Variable | Beschreibung | Standard |
|---|---|---|
| `LLM_API_KEY` | API-Key für den LLM (erforderlich) | – |
| `LLM_BASE_URL` | Base URL der API | `https://api.openai.com/v1` |
| `LLM_MODEL` | Modell-Name | `gpt-4o` |
| `PORT` | Web-Port | `8000` |

**Ohne API-Key** kann die App nur den Health-Check anzeigen. Ein LLM ist zwingend erforderlich.

## API Endpunkte

| Methode | Pfad | Beschreibung |
|---|---|---|
| `GET` | `/api/health` | Health-Check |
| `GET` | `/api/config` | LLM-Konfigurationsstatus |
| `POST` | `/api/generate` | Text → BPMN generieren |

### POST /api/generate

**Request:**
```json
{
  "text": "Ein Kunde stellt einen Urlaubsantrag..."
}
```

**Response:**
```json
{
  "success": true,
  "bpmn_xml": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<bpmn:definitions ...",
  "notes": {
    "assumptions": ["Annahme 1"],
    "open_questions": ["Frage 1?"],
    "improvements": ["Vorschlag 1"]
  },
  "process_definition": { ... }
}
```

## Entwickeln

### Lokal ohne Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt

# Node.js für ELK.js-Layout (einmalig)
cd backend && npm install && cd ..

# API-Key setzen
export LLM_API_KEY=...
export LLM_MODEL=gpt-4o

# Starten (mit Hot-Reload)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

## Technologie-Stack

- **Backend:** Python / FastAPI / OpenAI SDK
- **Layout:** ELK.js (Sugiyama) via Node.js — Spine-Gap-Routing für kreuzungsfreie Kanten
- **Frontend:** HTML / Vanilla JS / CSS (kein Framework)
- **Editor:** bpmn-js (BPMN 2.0 Modellierung im Browser)
- **Sprache:** Web Speech API
- **Container:** Docker / Docker Compose

## Tests

```bash
# Einmalig: Test-Abhängigkeiten installieren
pip install -r backend/requirements-dev.txt

# Einmalig: ELK.js installieren (falls nicht schon geschehen)
cd backend && npm install && cd ..

# Alle Tests ausführen
python -m pytest tests/ -v
```

## Lizenz

**MIT License** — Copyright (c) 2026 Guido Esser

- ✅ **Self-hosting** für eigene Zwecke: kostenlos und unbegrenzt
- ✅ **Modifizieren und forken** erlaubt
- ✅ **Kommerzielle Nutzung und SaaS** erlaubt — unter Beibehaltung des Copyright-/Lizenzhinweises

Siehe [LICENSE](./LICENSE) für den vollständigen Text.
