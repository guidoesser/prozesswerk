# Copyright (c) 2026 Guido Esser
# Licensed under the MIT License — see LICENSE file for details.

import os
import sys
import json
import logging
import mimetypes
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from . import generate_bpmn
    from . import llm_client
except ImportError:
    import generate_bpmn
    import llm_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Prozesswerk")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Path to frontend
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
if not os.path.isdir(FRONTEND_DIR):
    logger.warning(f"Frontend directory not found at {FRONTEND_DIR}")


# ═══════════════════════════════════════════════════════════════
# API Routes
# ═══════════════════════════════════════════════════════════════

class GenerateRequest(BaseModel):
    text: str
    existing_definition: Optional[dict] = None


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/config")
async def get_config():
    return {
        "llm_configured": llm_client.is_configured(),
        "llm_model": os.getenv("LLM_MODEL", "gpt-4o"),
        "llm_base_url": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
    }


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text darf nicht leer sein")

    try:
        logger.info(f"Generating BPMN for: {req.text[:100]}...")

        llm_result = llm_client.generate_bpmn_from_text(
            req.text,
            existing_definition=req.existing_definition
        )
        process_def = llm_result.get("process_definition", {})

        if not process_def.get("lanes"):
            process_def = {
                "name": "Prozess",
                "id": "Process_1",
                "lanes": [{"name": "Organisation", "id": "Lane_1", "elements": []}],
                "flows": [],
                "end_events": []
            }

        try:
            bpmn_xml = generate_bpmn.generate_xml(process_def)
        except Exception as e:
            logger.error(f"BPMN XML generation failed: {e}")
            bpmn_xml = f"<!-- BPMN XML could not be generated: {e} -->"

        notes = llm_result.get("notes", {"assumptions": [], "open_questions": [], "improvements": []})

        return {
            "success": True,
            "bpmn_xml": bpmn_xml,
            "notes": notes,
            "process_definition": process_def,
        }

    except llm_client.LLMNotConfiguredError:
        raise HTTPException(status_code=503, detail="LLM nicht konfiguriert. Bitte LLM_API_KEY in .env setzen.")
    except ValueError as e:
        logger.error(f"Generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Interner Fehler: {str(e)}")


# ═══════════════════════════════════════════════════════════════
# Frontend — Catch-all für alle Nicht-API-Routen
# ═══════════════════════════════════════════════════════════════

@app.get("/{path:path}")
async def serve_frontend(path: str, request: Request):
    """Serve frontend static files. Falls back to index.html for SPA routing."""
    if not os.path.isdir(FRONTEND_DIR):
        return HTMLResponse("<h1>Frontend nicht gefunden</h1>", status_code=500)

    # Check if the requested path is a static file
    file_path = os.path.join(FRONTEND_DIR, path) if path else os.path.join(FRONTEND_DIR, "index.html")

    # Security: prevent directory traversal
    real_path = os.path.realpath(file_path)
    if not real_path.startswith(os.path.realpath(FRONTEND_DIR)):
        raise HTTPException(status_code=403, detail="Forbidden")

    # If path is empty or ends with /, serve index.html
    if not path or os.path.isdir(real_path):
        real_path = os.path.join(FRONTEND_DIR, "index.html")

    # Serve existing files
    if os.path.isfile(real_path):
        mime_type, _ = mimetypes.guess_type(real_path)
        return FileResponse(real_path, media_type=mime_type)

    # SPA fallback: serve index.html for non-file routes
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)

    raise HTTPException(status_code=404, detail="Not found")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
