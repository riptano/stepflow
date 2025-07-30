#!/bin/bash
# Test script for production model serving demo

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🧪 Testing Production Model Serving Demo"
echo "========================================"

echo ""
echo "1️⃣  Testing Development Mode (Direct Run)..."
echo "============================================="
"$SCRIPT_DIR/run-dev-direct.sh" text

echo ""
echo "2️⃣  Testing Development Mode (Serve/Submit)..."
echo "==============================================="
"$SCRIPT_DIR/run-dev.sh" text

echo ""
echo "3️⃣  Testing Production Mode..."
echo "==============================="
"$SCRIPT_DIR/run-prod.sh" text

echo ""
echo "4️⃣  Testing Batch Processing (Direct Run)..."
echo "============================================="
"$SCRIPT_DIR/run-dev-direct.sh" batch

echo ""
echo "5️⃣  Testing Multimodal Processing (Production)..."
echo "================================================="
"$SCRIPT_DIR/run-prod.sh" multimodal

echo ""
echo "✅ All tests completed successfully!"
echo ""
echo "🧹 Cleaning up..."
cd "$(dirname "$SCRIPT_DIR")"
docker-compose down

echo "✨ Demo test suite completed!"