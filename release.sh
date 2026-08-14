#!/usr/bin/env bash
# release.sh — Production-Release für prozesswerk
# Nutzung:  ./release.sh <version>
# Beispiel: ./release.sh 1.2.0
#
# Ablauf:
#   1. Stelle sicher, dass wir auf main sind
#   2. Führe lokale Tests aus (müssen grün sein)
#   3. Update production-Branch auf aktuellen main-Stand
#   4. Tagge mit Version + baue Docker-Image
#   5. Push production + Tags + Docker-Image

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ─── Version prüfen ───────────────────────────────────────────────
VERSION="${1:-}"
if [ -z "$VERSION" ]; then
    error "Version-Argument erforderlich. Nutzung: ./release.sh <version>  (z.B. ./release.sh 1.2.0)"
fi

# Semver-Validierung
if ! echo "$VERSION" | grep -qP '^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$'; then
    error "Version '$VERSION' entspricht nicht semver (z.B. 1.2.3 oder 1.2.3-beta.1)"
fi

# ─── Auf main-Branch sicherstellen ────────────────────────────────
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" != "main" ]; then
    error "Du musst auf 'main' sein, um ein Release zu machen. Aktuell: '$BRANCH'"
fi

# Ungepushte Commits?
UNPUSHED=$(git rev-list origin/main..HEAD --count 2>/dev/null || echo 0)
if [ "$UNPUSHED" -gt 0 ]; then
    warn "main hat $UNPUSHED ungepushte Commits. Push zuerst mit 'git push origin main'."
    read -rp "Trotzdem fortfahren? (j/N): " cont
    [[ "$cont" =~ ^[jJ] ]] || exit 0
fi

info "Starte Release v$VERSION von main → production"

# ─── 1. Tests ausführen ───────────────────────────────────────────
info "Führe Tests aus..."
if [ -d "tests" ] && [ -n "$(ls tests/test_*.py 2>/dev/null)" ]; then
    if command -v uv &>/dev/null; then
        uv run pytest tests/ -v
    else
        python -m pytest tests/ -v
    fi
    info "Alle Tests bestanden ✓"
else
    warn "Keine Tests gefunden (tests/test_*.py). Test-Gate wird übersprungen."
    warn "Füge Tests hinzu, damit das Gate aktiv wird."
fi

# ─── 2. Bestätigung ─────────────────────────────────────────────────
echo ""
info "Tests bestanden ✓ (oder keine Tests vorhanden)"
echo ""
echo -e "  ${YELLOW}▶${NC} Merge main → production"
echo -e "  ${YELLOW}▶${NC} Tag: v$VERSION"
echo -e "  ${YELLOW}▶${NC} Docker: ghcr.io/guidoesser/prozesswerk:$VERSION"
echo ""

read -rp "Push auf production? (j/N): " confirm
if [[ ! "$confirm" =~ ^[jJ] ]]; then
    info "Abgebrochen. Nichts wurde gepusht."
    git checkout main 2>/dev/null
    exit 0
fi

# ─── 3. Production-Branch updaten ──────────────────────────────────
info "Update production-Branch..."
git fetch origin production
git checkout production
git merge main --no-edit || error "Merge-Konflikt! Bitte manuell lösen."
git push origin production

info "Production-Branch ist jetzt auf main-Stand"

# ─── 4. Taggen ─────────────────────────────────────────────────────
git checkout main
TAG="v$VERSION"
if git rev-parse "$TAG" >/dev/null 2>&1; then
    error "Tag '$TAG' existiert bereits."
fi
git tag -a "$TAG" -m "Release $TAG"
git push origin "$TAG"
info "Tag $TAG erstellt und gepusht"

# ─── 5. Docker-Image bauen ─────────────────────────────────────────
IMAGE="ghcr.io/guidoesser/prozesswerk"
info "Baue Docker-Image: $IMAGE:$VERSION"

docker build -t "$IMAGE:$VERSION" -t "$IMAGE:latest" .

# Publish (optional — wenn GitHub Token gesetzt)
if [ -n "${GITHUB_TOKEN:-}" ]; then
    echo "$GITHUB_TOKEN" | docker login ghcr.io -u guidoesser --password-stdin
    docker push "$IMAGE:$VERSION"
    docker push "$IMAGE:latest"
    info "Docker-Image gepusht: $IMAGE:$VERSION + $IMAGE:latest"
else
    warn "GITHUB_TOKEN nicht gesetzt. Image nur lokal gebaut, nicht gepusht."
    warn "Setze: export GITHUB_TOKEN=$(gh auth token)  (nach gh auth login)"
fi

# ─── Zurück auf main ──────────────────────────────────────────────
git checkout main

echo ""
echo -e "${GREEN}═══ Release v$VERSION abgeschlossen ═══${NC}"
echo "  Branch:       production (synced mit main)"
echo "  Tag:          $TAG"
echo "  Docker:       $IMAGE:$VERSION"
echo ""
