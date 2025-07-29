# LangChain Integration Example

This example demonstrates the integration of LangChain with StepFlow, showcasing three different approaches for using LangChain runnables as StepFlow components.

## Overview

The LangChain integration allows you to:

1. **Registry Approach**: Use `@server.langchain_component` decorator to register LangChain runnable factories as StepFlow components
2. **Direct Components**: Execute LangChain runnables directly using `/langchain/invoke`
3. **UDF Approach**: Store LangChain runnables as blobs and execute them via `/langchain/udf` (currently has type annotation issues)

## Prerequisites

- Rust (for building StepFlow)
- Python 3.13+ with uv
- LangChain core library

## Setup

1. **Install dependencies**:
   ```bash
   cd ../../sdks/python
   uv add --group dev langchain-core
   ```

2. **Build StepFlow**:
   ```bash
   cd ../../stepflow-rs
   cargo build
   ```

## Running the Example

### Simple Example (Recommended)

The `simple_workflow.yaml` demonstrates the registry and direct component approaches:

```bash
# Run the working example
../../stepflow-rs/target/debug/stepflow run \
  --flow=simple_workflow.yaml \
  --input=input.json \
  --config=stepflow-config.yml
```

### Full Example

The `workflow.yaml` includes all three approaches but currently has an issue with the UDF component:

```bash
# Run the full example (UDF component will fail)
../../stepflow-rs/target/debug/stepflow run \
  --flow=workflow.yaml \
  --input=input.json \
  --config=stepflow-config.yml
```

## Components Demonstrated

### 1. Registry Approach (`@server.langchain_component`)

These components are defined in `langchain_server.py`:

- **`/text_analyzer`**: Analyzes text and returns word count, character count, etc.
- **`/sentiment_classifier`**: Simple sentiment analysis using keyword matching
- **`/math_operations`**: Parallel mathematical operations (sum, product, power)

Example usage in workflow:
```yaml
- id: analyze_text
  component: /text_analyzer
  input:
    input:
      text: "Your text here"
    execution_mode: invoke
```

### 2. Direct Components

- **`/langchain/invoke`**: Execute any LangChain runnable from its serialized definition
- **`/demo_direct_langchain`**: Helper component that prepares runnable definitions

### 3. Helper Components

- **`/create_langchain_blob`**: Creates blobs containing LangChain runnables for UDF usage

## Sample Input

```json
{
  "text": "This is a great example of LangChain integration with StepFlow!",
  "numbers": [1, 2, 3, 4, 5, 10, 15]
}
```

## Expected Output

```json
{
  "outcome": "success",
  "result": {
    "text_analysis": {
      "word_count": 18,
      "char_count": 114,
      "char_count_no_spaces": 97,
      "sentence_count": 1,
      "uppercase_ratio": 0.05263157894736842
    },
    "sentiment": {
      "sentiment": "positive",
      "confidence": 0.6666666666666666
    },
    "math_results": {
      "sum": 13,
      "product": 30,
      "power": 1000
    },
    "direct_component_demo": {
      "operation": "calculate_stats",
      "runnable_ready": true,
      "invoke_input_prepared": {
        "runnable_definition": {...},
        "input": {"numbers": [1,2,3,4,5,10,15]},
        "execution_mode": "invoke"
      }
    }
  }
}
```

## Architecture

### Configuration

The `stepflow-config.yml` configures:
- **`langchain` plugin**: Python server running the LangChain components
- **Routing**: All components first try the langchain plugin, then fall back to builtin

### LangChain Server

The `langchain_server.py` file demonstrates:
- Component registration using `@server.langchain_component`
- Integration with StepFlow's bidirectional communication
- Type-safe component definitions with msgspec

### Key Features

1. **Async Compatibility**: Both StepFlow and LangChain use async/await patterns
2. **Type Safety**: msgspec integration with JSON Schema support
3. **Bidirectional Communication**: Components can access StepFlow runtime services via `StepflowContext`
4. **Multiple Execution Modes**: Support for invoke, batch, and stream operations
5. **Automatic Schema Generation**: LangChain runnable schemas are automatically extracted

## Known Issues

- **UDF Component**: The `/langchain/udf` component currently has type annotation issues with `LangChainUdfInput`
- **Serialization**: Some complex LangChain runnables may not serialize/deserialize properly

## Next Steps

To extend this example:

1. **Add more LangChain integrations**: Try different runnable types (chains, agents, etc.)
2. **Custom components**: Create more sophisticated business logic components
3. **Streaming support**: Implement streaming for long-running LangChain operations
4. **Fix UDF issues**: Resolve the type annotation problems with the UDF approach

## Files

- `langchain_server.py`: Python server with LangChain components
- `simple_workflow.yaml`: Working example with registry and direct approaches
- `workflow.yaml`: Full example including UDF approach (has issues)
- `stepflow-config.yml`: StepFlow configuration
- `input.json`: Sample input data
- `README.md`: This documentation