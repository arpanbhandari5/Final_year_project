#!/usr/bin/env bash
#
# Prayash — Startup Script (Unix/macOS)
# =======================================
# 1. Trains or verifies the ML model artifacts
# 2. Starts the Flask development server
#
# Usage:
#   ./start.sh              # Default mode: train + serve
#   ./start.sh --train-only # Only train / verify artifacts
#   ./start.sh --serve-only # Only start the server (skip training)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

info()  { echo -e "\033[1;34m[INFO]\033[0m $*"; }
ok()    { echo -e "\033[1;32m[OK]\033[0m   $*"; }
error() { echo -e "\033[1;31m[ERR]\033[0m  $*"; }
step()  { echo; echo -e "\033[1m── $* ──\033[0m"; }

train_model() {
    step "ML Model Training"
    if [ -f "ml_models/model.pkl" ] && [ -f "ml_models/courses.pkl" ]; then
        info "Model artifacts already exist at ml_models/ — skipping training."
        return 0
    fi
    info "Model artifacts not found. Training from scratch..."
    python train_model.py
    if [ -f "ml_models/model.pkl" ] && [ -f "ml_models/courses.pkl" ]; then
        ok "Model artifacts created successfully."
    else
        error "Model training failed — artifacts are missing."
        exit 1
    fi
}

serve() {
    step "Starting Prayash Flask Server"
    info "Listening on 0.0.0.0:${PORT:-5000}"
    python app.py
}

# ── Parse Args ────────────────────────────────────────────────────
case "${1:-all}" in
    --train-only) train_model ;;
    --serve-only) serve ;;
    *)            train_model && serve ;;
esac
