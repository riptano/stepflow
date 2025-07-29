#!/usr/bin/env python3
# Licensed to the Apache Software Foundation (ASF) under one or more contributor
# license agreements.  See the NOTICE file distributed with this work for
# additional information regarding copyright ownership.  The ASF licenses this
# file to you under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

"""
Examples of using LangChain integration with StepFlow.

This demonstrates all three approaches:
1. UDF-style: LangChain runnables stored as blobs
2. Direct components: Using /langchain/invoke 
3. Registry: Using @server.langchain_component decorator

Run with: python examples/langchain_examples.py
"""

from stepflow_py import StepflowStdioServer, StepflowContext
import msgspec
import asyncio
import json

# Only run examples if LangChain is available
try:
    from langchain_core.runnables import RunnableLambda, RunnableParallel
    from langchain_core.prompts import ChatPromptTemplate
    from stepflow_py.langchain_udf import create_langchain_runnable_blob
    LANGCHAIN_AVAILABLE = True
except ImportError:
    print("LangChain not available. Install with: pip install stepflow-py[langchain]")
    LANGCHAIN_AVAILABLE = False
    exit(1)

# Create the server
server = StepflowStdioServer()

if LANGCHAIN_AVAILABLE:
    # Example 1: Registry approach - @server.langchain_component decorator
    @server.langchain_component(name="text_analyzer")
    def create_text_analyzer():
        """Analyze text and return various metrics."""
        def analyze_text(text_input):
            text = text_input["text"]
            return {
                "word_count": len(text.split()),
                "char_count": len(text),
                "char_count_no_spaces": len(text.replace(" ", "")),
                "sentence_count": len([s for s in text.split(".") if s.strip()]),
                "uppercase_ratio": sum(1 for c in text if c.isupper()) / len(text) if text else 0,
            }
        
        return RunnableLambda(analyze_text)

    @server.langchain_component(name="math_operations")
    def create_math_operations():
        """Perform parallel math operations on numbers."""
        def add_numbers(input_data):
            return input_data["a"] + input_data["b"]
        
        def multiply_numbers(input_data):
            return input_data["a"] * input_data["b"]
        
        def power_operation(input_data):
            return input_data["a"] ** input_data["b"]
        
        return RunnableParallel({
            "sum": RunnableLambda(add_numbers),
            "product": RunnableLambda(multiply_numbers),
            "power": RunnableLambda(power_operation),
        })

    @server.langchain_component()  # Uses function name
    def sentiment_classifier():
        """Simple sentiment classifier."""
        def classify_sentiment(input_data):
            text = input_data["text"].lower()
            
            positive_words = ["good", "great", "excellent", "amazing", "wonderful", "fantastic"]
            negative_words = ["bad", "terrible", "awful", "horrible", "hate", "worst"]
            
            positive_score = sum(1 for word in positive_words if word in text)
            negative_score = sum(1 for word in negative_words if word in text)
            
            if positive_score > negative_score:
                return {"sentiment": "positive", "confidence": positive_score / (positive_score + negative_score + 1)}
            elif negative_score > positive_score:
                return {"sentiment": "negative", "confidence": negative_score / (positive_score + negative_score + 1)}
            else:
                return {"sentiment": "neutral", "confidence": 0.5}
        
        return RunnableLambda(classify_sentiment)

    # Example 2: Helper component to create LangChain runnable blobs for UDF usage
    class CreateLangChainBlobInput(msgspec.Struct):
        runnable_type: str  # "text_processor", "data_transformer", etc.
        input_schema: dict
        output_schema: dict | None = None

    @server.component
    async def create_langchain_blob(
        input: CreateLangChainBlobInput, 
        context: StepflowContext
    ) -> dict:
        """Create a blob containing a LangChain runnable for UDF usage."""
        
        # Create different types of runnables based on the type
        if input.runnable_type == "text_processor":
            def process_text(data):
                text = data["text"]
                words = text.split()
                return {
                    "processed_text": " ".join(word.capitalize() for word in words),
                    "word_count": len(words),
                    "original_length": len(text)
                }
            runnable = RunnableLambda(process_text)
            
        elif input.runnable_type == "data_transformer":
            def transform_data(data):
                numbers = data["numbers"]
                return {
                    "sum": sum(numbers),
                    "average": sum(numbers) / len(numbers) if numbers else 0,
                    "max": max(numbers) if numbers else 0,
                    "min": min(numbers) if numbers else 0,
                    "count": len(numbers)
                }
            runnable = RunnableLambda(transform_data)
            
        elif input.runnable_type == "string_formatter":
            def format_string(data):
                template = data.get("template", "Hello {name}!")
                values = data.get("values", {})
                try:
                    return {"formatted": template.format(**values)}
                except KeyError as e:
                    return {"error": f"Missing template variable: {e}"}
            runnable = RunnableLambda(format_string)
            
        else:
            raise ValueError(f"Unknown runnable type: {input.runnable_type}")
        
        # Create the blob data
        blob_data = create_langchain_runnable_blob(
            runnable,
            input_schema=input.input_schema,
            output_schema=input.output_schema,
            execution_mode="invoke"
        )
        
        # Store as blob
        blob_id = await context.put_blob(blob_data)
        
        return {
            "blob_id": blob_id,
            "runnable_type": input.runnable_type,
            "schemas": {
                "input": input.input_schema,
                "output": input.output_schema or blob_data["output_schema"]
            }
        }

    # Example 3: Demo component showing direct /langchain/invoke usage
    class DirectLangChainInput(msgspec.Struct):
        operation: str  # "reverse_text", "calculate_stats"
        data: dict

    @server.component
    async def demo_direct_langchain(
        input: DirectLangChainInput,
        context: StepflowContext
    ) -> dict:
        """Demonstrate using /langchain/invoke component directly."""
        
        # Create a simple runnable based on operation
        if input.operation == "reverse_text":
            def reverse_text(data):
                return {"reversed": data["text"][::-1]}
            runnable = RunnableLambda(reverse_text)
            
        elif input.operation == "calculate_stats":
            def calc_stats(data):
                numbers = data["numbers"]
                if not numbers:
                    return {"error": "No numbers provided"}
                return {
                    "sum": sum(numbers),
                    "mean": sum(numbers) / len(numbers),
                    "median": sorted(numbers)[len(numbers) // 2],
                    "range": max(numbers) - min(numbers)
                }
            runnable = RunnableLambda(calc_stats)
        else:
            raise ValueError(f"Unknown operation: {input.operation}")
        
        # Serialize the runnable for direct execution
        from stepflow_py.langchain_integration import serialize_runnable
        runnable_definition = serialize_runnable(runnable)
        
        # Use the direct /langchain/invoke component
        # Note: In a real workflow, this would be done via the workflow YAML
        # This is just to demonstrate the component structure
        invoke_input = {
            "runnable_definition": runnable_definition,
            "input": input.data,
            "execution_mode": "invoke"
        }
        
        return {
            "operation": input.operation,
            "runnable_ready": True,
            "invoke_input_prepared": invoke_input,
            "note": "In a real workflow, use /langchain/invoke component with this invoke_input"
        }

if __name__ == "__main__":
    print("LangChain StepFlow Integration Examples")
    print("======================================")
    print()
    print("This server demonstrates three approaches to LangChain integration:")
    print("1. Registry: @server.langchain_component decorator")
    print("2. UDF: LangChain runnables stored as blobs")  
    print("3. Direct: /langchain/invoke component")
    print()
    print("Available components:")
    
    components = server.get_components()
    for name, component in components.items():
        print(f"  - {name}: {component.description or 'No description'}")
    
    print()
    print("Starting StepFlow server...")
    server.run()