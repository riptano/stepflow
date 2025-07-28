#!/bin/bash
# Development mode runner using direct `run` command
# Best for fast iteration and workflow development

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLE_DIR="$(dirname "$SCRIPT_DIR")"
STEPFLOW_DIR="$(dirname "$(dirname "$EXAMPLE_DIR")")/stepflow-rs"

echo "🚀 Running Production Model Serving Demo (Direct Run Mode)"
echo "=========================================================="
echo "Using direct 'run' command for fast iteration"

# Check dependencies
echo "📦 Checking dependencies..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

echo "✅ Dependencies satisfied"

# Navigate to example directory for model server execution
cd "$EXAMPLE_DIR"

echo "🔧 Configuration: Development (direct run with subprocesses)"
echo "📂 Working directory: $EXAMPLE_DIR"
echo "🏗️  StepFlow source: $STEPFLOW_DIR"

# Choose input file
INPUT_FILE="sample_input_text.json"
if [ "$1" = "multimodal" ]; then
    INPUT_FILE="sample_input_multimodal.json"
elif [ "$1" = "batch" ]; then
    INPUT_FILE="sample_input_batch.json"
fi

echo "📄 Using input: $INPUT_FILE"
echo ""

# Run the workflow directly
echo "▶️  Executing workflow with direct run..."
cd "$STEPFLOW_DIR"
cargo run -- run \
    --flow="../examples/production-model-serving/ai_pipeline_workflow.yaml" \
    --input="../examples/production-model-serving/$INPUT_FILE" \
    --config="../examples/production-model-serving/stepflow-config-dev.yml"

echo ""
echo "✅ Direct run execution completed!"
echo ""
echo "💡 To test other input types:"
echo "   $0 multimodal  # Test with image processing"
echo "   $0 batch       # Test batch processing"
echo ""
echo "🔄 For persistent server testing, use:"
echo "   ./run-dev.sh   # Uses serve/submit pattern"