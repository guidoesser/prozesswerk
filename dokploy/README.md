# Dokploy Deployment

## Variante A: Compose-Datei (empfohlen)

1. Dokploy → Project → **Compose** → Type: **Docker Compose**
2. Compose Path: `./docker-compose.prod.yml`
3. Environment Variables setzen (siehe unten)

## Variante B: Base64 Import

1. Dokploy → **Compose** → **Advanced** → **Base64 import**
2. Inhalt von `import.txt` einfügen
3. Domain und API-Key im Wizard setzen

## Environment Variables

| Variable | Beschreibung |
|---|---|
| `LLM_API_KEY` | API-Key für OpenAI-kompatiblen Endpunkt |
| `LLM_BASE_URL` | Base URL (Default: `https://api.openai.com/v1`) |
| `LLM_MODEL` | Modell (Default: `gpt-4o`) |

## Updates

Neue Releases mit `./release.sh <version>` bauen das Image `:latest` neu.
In Dokploy: Service → **Redeploy** um das neueste Image zu ziehen.

Für pinned Version: Image-Tag auf `:1.0.0` o.ä. ändern.
