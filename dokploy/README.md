# Dokploy Deployment

Zwei Wege, Prozesswerk in Dokploy laufen zu lassen. Für den schnellen Start nimm **Weg 1** (Dokploy baut das Image selbst — kein vorab gebautes Image nötig).

## Weg 1: Git-Provider (empfohlen, baut selbst)

1. Dokploy → **Create Project** (z. B. „Prozesswerk")
2. Projekt öffnen → **Create Service** → **Compose**
3. Compose Type: **Docker Compose**
4. Provider: **GitHub** (GitHub-App einmalig verbinden)
5. Repository: `guidoesser/prozesswerk`, Branch: `main`
6. **Compose Path:** `./docker-compose.dokploy.yml`
7. Speichern, dann unter **Environment** die Variablen setzen (siehe unten)
8. Optional Domain: Tab **Domains** → Domain anlegen, Port `8000`
9. **Deploy**

Dokploy klont das Repo und baut das Image direkt — kein `ghcr.io`-Image nötig.

## Weg 2: Vorgebautes Image (ghcr.io)

Voraussetzung: Image `ghcr.io/guidoesser/prozesswerk:latest` muss existieren.
Erzeugen via `./release.sh <version>` (lokal) — oder Push auf `production`/Tag, dann baut die CI das Image automatisch.

Danach in Dokploy:

1. Create Project → Create Service → **Compose**
2. Compose Path: `./docker-compose.prod.yml`
3. Environment-Variablen setzen, Domain anlegen, Deploy

### Base64-Import (Alternative zu Weg 2)

1. Create Service → Compose → **Advanced** → **Import from Base64**
2. Inhalt von `dokploy/import.txt` einfügen
3. Domain und API-Key im Wizard setzen

## Environment Variables

| Variable | Beschreibung |
|---|---|
| `LLM_API_KEY` | API-Key für OpenAI-kompatiblen Endpunkt (erforderlich) |
| `LLM_BASE_URL` | Base URL (Default: `https://api.openai.com/v1`) |
| `LLM_MODEL` | Modell (Default: `gpt-4o`) |

## Updates

- **Weg 1:** Push auf `main` → in Dokploy **Redeploy** (baut neu aus dem Repo)
- **Weg 2:** Neues Release via `./release.sh <version>` → Image `:latest` → **Redeploy**
