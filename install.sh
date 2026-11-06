#!/usr/bin/env bash
# Copyright 2026 Google LLC
# Apache-2.0
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${HOME}/.gemini/config/plugins/bean-core"

echo "☕ Installing bean-core plugin..."
mkdir -p "${TARGET_DIR}"
cp -r "${SCRIPT_DIR}/plugin.json" "${TARGET_DIR}/"
cp -r "${SCRIPT_DIR}/stages.yaml" "${TARGET_DIR}/"
cp -r "${SCRIPT_DIR}/README.md" "${TARGET_DIR}/" 2>/dev/null || true
cp -r "${SCRIPT_DIR}/skills" "${TARGET_DIR}/"
cp -r "${SCRIPT_DIR}/agents" "${TARGET_DIR}/" 2>/dev/null || true
cp -r "${SCRIPT_DIR}/rules" "${TARGET_DIR}/" 2>/dev/null || true
cp -r "${SCRIPT_DIR}/hooks.json" "${TARGET_DIR}/" 2>/dev/null || true
cp -r "${SCRIPT_DIR}/scripts" "${TARGET_DIR}/" 2>/dev/null || true

echo "✅ bean-core installed successfully to ${TARGET_DIR}."
