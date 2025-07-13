#!/usr/bin/env python3
"""
Langflow component server with generic wrapper for native Langflow components.

This demonstrates how to create a generic wrapper that:
1. Uses native Langflow types (Data, Message, DataFrame)
2. Dynamically wraps any Langflow component
3. Automatically handles type conversion and schema introspection
"""

from stepflow_langflow import StepflowLangflowServer
from stepflow_sdk import StepflowContext
import msgspec
from typing import Dict, Any, List, Optional, Union
import os
import inspect
import sys
import json

# Import actual Langflow components and types
from langflow.components.openai.openai_chat_model import OpenAIModelComponent
from langflow.components.processing import PromptComponent
from langflow.schema.data import Data
from langflow.schema.message import Message
from langflow.schema.dataframe import DataFrame
from langflow.custom.custom_component.component import Component

# Create the server
server = StepflowLangflowServer(default_protocol_prefix="langflow")

import os

# Helper functions for native Langflow type handling
def _serialize_langflow_object(obj):
    """Serialize Langflow objects with type metadata for proper deserialization."""
    if isinstance(obj, Message):
        serialized = obj.model_dump(mode='json')
        serialized['__langflow_type__'] = 'Message'
        return serialized
    elif isinstance(obj, Data):
        serialized = obj.model_dump(mode='json')
        serialized['__langflow_type__'] = 'Data'
        return serialized
    elif isinstance(obj, DataFrame):
        # Handle Langflow's custom DataFrame
        try:
            # Use the to_data_list method to preserve Data objects
            data_list = obj.to_data_list() if hasattr(obj, 'to_data_list') else obj.to_dict('records')
            return {
                "__langflow_type__": "DataFrame",
                "data": [item.model_dump(mode='json') if hasattr(item, 'model_dump') else item for item in data_list],
                "text_key": getattr(obj, 'text_key', 'text'),
                "default_value": getattr(obj, 'default_value', '')
            }
        except:
            # Fallback to basic pandas serialization
            return {
                "__langflow_type__": "DataFrame", 
                "data": obj.to_dict('records') if hasattr(obj, 'to_dict') else str(obj)
            }
    elif isinstance(obj, (str, int, float, bool, list, dict, type(None))):
        # Simple serializable types - pass through
        return obj
    else:
        # Complex object that can't be serialized - use deferred execution
        print(f"🔍 SERIALIZE: Complex object detected: {type(obj)}, using deferred execution", file=sys.stderr)
        return _create_deferred_execution(obj)

def _create_deferred_execution(obj):
    """Create a deferred execution wrapper for complex objects."""
    obj_type = type(obj)
    module_name = obj_type.__module__
    class_name = obj_type.__name__
    
    # Try to extract constructor arguments from the object
    config = {}
    
    # Common patterns for extracting config from objects
    if hasattr(obj, '__dict__'):
        # Extract simple attributes that look like constructor params
        for attr_name, attr_value in obj.__dict__.items():
            if not attr_name.startswith('_') and isinstance(attr_value, (str, int, float, bool, type(None))):
                config[attr_name] = attr_value
    
    # Special handling for known types
    if hasattr(obj, 'model') and isinstance(getattr(obj, 'model'), str):
        config['model'] = obj.model
    if hasattr(obj, 'openai_api_key') and isinstance(getattr(obj, 'openai_api_key'), str):
        config['openai_api_key'] = obj.openai_api_key
    
    # Generate the recreation code
    imports = f"from {module_name} import {class_name}"
    
    # Build constructor call
    if config:
        config_args = ', '.join([f"{k}={repr(v)}" for k, v in config.items()])
        recreation_code = f"{class_name}({config_args})"
    else:
        recreation_code = f"{class_name}()"
    
    deferred = {
        "__deferred_execution__": {
            "imports": imports,
            "recreation_code": recreation_code,
            "class_name": class_name,
            "module_name": module_name,
            "config": config,
            "original_type": f"{module_name}.{class_name}"
        }
    }
    
    return deferred

def _execute_deferred(deferred_info):
    """Execute deferred code to recreate a complex object."""
    try:
        
        # Create execution environment
        exec_globals = globals().copy()
        exec_locals = {}
        
        # Execute imports
        exec(deferred_info['imports'], exec_globals, exec_locals)
        
        # Execute recreation code
        recreated_obj = eval(deferred_info['recreation_code'], exec_globals, exec_locals)
        
        return recreated_obj
        
    except Exception as e:
        print(f"❌ DEFERRED: Failed to execute deferred code: {e}", file=sys.stderr)
        print(f"❌ DEFERRED: Imports: {deferred_info['imports']}", file=sys.stderr)
        print(f"❌ DEFERRED: Recreation code: {deferred_info['recreation_code']}", file=sys.stderr)
        raise RuntimeError(f"Failed to execute deferred object creation: {e}") from e

def _deserialize_to_langflow_type(obj, expected_type=None):
    """Deserialize objects back to Langflow types using type metadata."""
    if not isinstance(obj, dict):
        return obj
    
    # Check for explicit type metadata first
    langflow_type = obj.get('__langflow_type__')
    if langflow_type:
        # Remove the type metadata before creating the object
        obj_data = {k: v for k, v in obj.items() if k != '__langflow_type__'}
        
        if langflow_type == 'Message':
            return Message(**obj_data)
        elif langflow_type == 'Data':
            return Data(**obj_data)
        elif langflow_type == 'DataFrame':
            # Reconstruct Langflow's custom DataFrame
            try:
                # Import the custom DataFrame
                from langflow.schema.dataframe import DataFrame as LangflowDataFrame
                from langflow.schema.data import Data
                
                data_list = obj_data.get('data', [])
                text_key = obj_data.get('text_key', 'text')
                default_value = obj_data.get('default_value', '')
                
                # Convert back to Data objects if needed
                if data_list and isinstance(data_list[0], dict):
                    data_objects = [Data(**item) if '__langflow_type__' not in item else Data(**{k: v for k, v in item.items() if k != '__langflow_type__'}) for item in data_list]
                else:
                    data_objects = data_list
                
                return LangflowDataFrame(data=data_objects, text_key=text_key, default_value=default_value)
            except Exception as e:
                print(f"⚠️  Failed to reconstruct DataFrame, using raw data: {e}", file=sys.stderr)
                return obj_data.get('data', obj_data)
    
    # If no type metadata and no expected type, this is an error
    if expected_type is None:
        raise ValueError(f"Cannot deserialize object to Langflow type: missing __langflow_type__ metadata and no expected_type provided. Object keys: {list(obj.keys())}")
    
    # Use the explicitly provided expected type
    if expected_type == Message:
        return Message(**obj)
    elif expected_type == Data:
        return Data(**obj)
    
    return obj

# Simple demo component for testing
@server.component
def echo_component(input: Dict[str, Any]) -> Dict[str, Any]:
    """Simple echo component for testing."""
    return {"echo": input, "message": "Echo component received your data"}

# UDF Executor Component
@server.component
async def udf_executor(input: Dict[str, Any], context: StepflowContext) -> Dict[str, Any]:
    """UDF executor that properly handles Langflow component class instantiation."""
    
    
    # Get blob_id and fetch the UDF data
    blob_id = input.get('blob_id')
    if not blob_id:
        return {"error": "No blob_id provided", "details": "UDF executor requires blob_id"}
    
    try:
        blob_data = await context.get_blob(blob_id)
    except Exception as e:
        return {"error": f"Failed to fetch blob {blob_id}", "details": str(e)}
    
    # Extract UDF components from the blob data
    code = blob_data.get('code', '')
    template = blob_data.get('template', {})
    component_type = blob_data.get('component_type', '')
    outputs = blob_data.get('outputs', [])
    selected_output = blob_data.get('selected_output')
    
    # Get runtime inputs from the input (these come from other workflow steps)
    runtime_inputs = input.get('input', {})
    
    
    
    try:
        # Execute the Langflow component with proper class handling
        result = await _execute_langflow_component(
            code=code,
            template=template,
            component_type=component_type,
            outputs=outputs,
            selected_output=selected_output,
            runtime_inputs=runtime_inputs
        )
        
        # Serialize result for StepFlow protocol, but preserve type info for deserialization
        serialized_result = _serialize_langflow_object(result)
        return {"result": serialized_result}
        
    except Exception as e:
        # FAIL FAST: Re-raise the exception instead of returning error objects
        # This prevents error propagation through the workflow and fails immediately
        raise RuntimeError(f"Component {component_type} failed: {str(e)}") from e

async def _execute_langflow_component(
    code: str, 
    template: Dict[str, Any], 
    component_type: str, 
    outputs: List[Dict[str, Any]], 
    selected_output: Optional[str],
    runtime_inputs: Dict[str, Any]
) -> Any:
    """Langflow component executor with proper class instantiation."""
    
    
    # 1. Set up execution environment 
    exec_globals = globals()
    # print(f"🌍 EXECUTE_COMPONENT: Using globals() for execution environment", file=sys.stderr)
    
    # 2. Execute the class definition
    try:
        exec(code, exec_globals)
    except Exception as e:
        raise ValueError(f"Failed to execute Langflow code: {e}")
    
    # 3. Find the component class
    component_class = _find_component_class(exec_globals, component_type)
    if not component_class:
        available_classes = [k for k, v in exec_globals.items() if isinstance(v, type)]
        print(f"❌ EXECUTE_COMPONENT: Component class '{component_type}' not found. Available: {available_classes}", file=sys.stderr)
        raise ValueError(f"Could not find component class for {component_type}")
    
    # 4. Determine the execution method from selected_output or outputs metadata
    execution_method = _determine_execution_method(outputs, selected_output)
    
    # 5. Instantiate the component (no parameters needed)
    print(f"🏗️  EXECUTE_COMPONENT: Instantiating component", file=sys.stderr)
    try:
        component_instance = component_class()
        print(f"✅ EXECUTE_COMPONENT: Component instantiated successfully", file=sys.stderr)
    except Exception as e:
        print(f"❌ EXECUTE_COMPONENT: Component instantiation failed: {e}", file=sys.stderr)
        raise ValueError(f"Failed to instantiate {component_type}: {e}")
    
    # 6. Configure the component using Langflow's official method
    print(f"⚙️  EXECUTE_COMPONENT: Configuring component with Langflow's set_attributes", file=sys.stderr)
    component_parameters = {}
    
    # Combine template and runtime inputs into parameters dict
    for key, field_def in template.items():
        if isinstance(field_def, dict) and 'value' in field_def:
            value = field_def['value']
            
            # Smart API key handling - detect placeholders and environment variable names
            if key == 'api_key' or key == 'openai_api_key' or key.endswith('_api_key'):
                # Check if value is empty, None, or looks like a placeholder/alias
                is_placeholder = (
                    value == '' or 
                    value is None or 
                    value in ['openaikey', 'anthropickey', 'googlekey'] or  # Common placeholders
                    (isinstance(value, str) and len(value) < 20 and not value.startswith('sk-'))  # Short non-key values
                )
                
                if is_placeholder:
                    # Determine which environment variable to use
                    env_var = None
                    
                    # Check if there's a provider field to determine which API key to use
                    provider_value = None
                    for provider_key, provider_field in template.items():
                        if provider_key == 'provider' and isinstance(provider_field, dict):
                            provider_value = provider_field.get('value', '').lower()
                            break
                    
                    # Map provider to environment variable
                    if provider_value == 'openai':
                        env_var = 'OPENAI_API_KEY'
                    elif provider_value == 'anthropic':
                        env_var = 'ANTHROPIC_API_KEY'
                    elif provider_value == 'google':
                        env_var = 'GOOGLE_API_KEY'
                    # Fallback based on field name if no provider
                    elif 'openai' in key.lower():
                        env_var = 'OPENAI_API_KEY'
                    elif 'anthropic' in key.lower():
                        env_var = 'ANTHROPIC_API_KEY'
                    elif 'google' in key.lower():
                        env_var = 'GOOGLE_API_KEY'
                    else:
                        # Default fallback
                        env_var = 'OPENAI_API_KEY'
                    
                    # Try to get the actual key from environment
                    actual_key = os.getenv(env_var)
                    if actual_key:
                        value = actual_key
                        print(f"📝 EXECUTE_COMPONENT: Using {env_var} from environment for {key} (placeholder: '{template[key].get('value')}', provider: {provider_value})", file=sys.stderr)
                    else:
                        print(f"⚠️  EXECUTE_COMPONENT: {env_var} not found in environment (placeholder: '{template[key].get('value')}', provider: {provider_value})", file=sys.stderr)
                else:
                    print(f"📝 EXECUTE_COMPONENT: Using provided API key for {key} (not a placeholder)", file=sys.stderr)
            
            component_parameters[key] = value
    
    # Add runtime inputs (these override template values)
    for key, value in runtime_inputs.items():
        # Check if this is a deferred execution object
        if isinstance(value, dict) and '__deferred_execution__' in value:
            # Execute deferred code to recreate the complex object
            actual_value = _execute_deferred(value['__deferred_execution__'])
            component_parameters[key] = actual_value
            print(f"🔄 EXECUTE_COMPONENT: Added runtime input {key} (deferred execution: {value['__deferred_execution__']['original_type']}, type: {type(actual_value).__name__})", file=sys.stderr)
        # Check if this is a serialized Langflow object that needs to be deserialized
        elif isinstance(value, dict) and '__langflow_type__' in value:
            # Serialized Langflow object - deserialize it
            actual_value = _deserialize_to_langflow_type(value)
            component_parameters[key] = actual_value
            print(f"🔄 EXECUTE_COMPONENT: Added runtime input {key} (deserialized {value['__langflow_type__']}, type: {type(actual_value).__name__})", file=sys.stderr)
        elif isinstance(value, str) and key in ['input_value', 'input_data']:
            # Special case: if we receive a plain string for input fields, wrap it in a Data object
            # This handles cases where upstream components return strings but downstream expects Data
            try:
                wrapped_value = Data(data={"text": value})
                component_parameters[key] = wrapped_value
                print(f"🔄 EXECUTE_COMPONENT: Added runtime input {key} (wrapped string in Data, type: {type(wrapped_value).__name__})", file=sys.stderr)
            except Exception as e:
                # If Data creation fails, fall back to original value
                print(f"⚠️  EXECUTE_COMPONENT: Failed to wrap string in Data object: {e}", file=sys.stderr)
                component_parameters[key] = value
                print(f"🔄 EXECUTE_COMPONENT: Added runtime input {key} (direct string fallback, type: {type(value).__name__})", file=sys.stderr)
        else:
            # Direct value - use as-is
            component_parameters[key] = value
            print(f"🔄 EXECUTE_COMPONENT: Added runtime input {key} (direct, type: {type(value).__name__})", file=sys.stderr)
    
    print(f"📋 EXECUTE_COMPONENT: Setting component parameters: {list(component_parameters.keys())}", file=sys.stderr)
    
        
    
    # Use Langflow's official configuration method
    if hasattr(component_instance, 'set_attributes'):
        component_instance._parameters = component_parameters
        component_instance.set_attributes(component_parameters)
        print(f"✅ EXECUTE_COMPONENT: Used Langflow's set_attributes method", file=sys.stderr)
    else:
        # Fallback - log warning but continue (most Langflow components should have set_attributes)
        print(f"⚠️  EXECUTE_COMPONENT: Component doesn't have set_attributes method", file=sys.stderr)
    
    # 7. Execute the specified method
    if not execution_method:
        print(f"❌ EXECUTE_COMPONENT: No execution method specified", file=sys.stderr)
        raise ValueError(f"No execution method specified in outputs for {component_type}")
    
    print(f"🔍 EXECUTE_COMPONENT: Checking if component has method '{execution_method}'", file=sys.stderr)
    if not hasattr(component_instance, execution_method):
        available_methods = [m for m in dir(component_instance) if not m.startswith('_')]
        print(f"❌ EXECUTE_COMPONENT: Method not found", file=sys.stderr)
        print(f"🔍 EXECUTE_COMPONENT: Available methods: {available_methods}", file=sys.stderr)
        raise ValueError(f"Component {component_type} does not have method '{execution_method}'")
    
    print(f"🚀 EXECUTE_COMPONENT: Executing method '{execution_method}'", file=sys.stderr)
    try:
        method = getattr(component_instance, execution_method)
        print(f"🔍 EXECUTE_COMPONENT: Method is coroutine: {inspect.iscoroutinefunction(method)}", file=sys.stderr)
        
        if inspect.iscoroutinefunction(method):
            result = await method()
        else:
            result = method()
            
        print(f"✅ EXECUTE_COMPONENT: Method execution successful", file=sys.stderr)
        print(f"📤 EXECUTE_COMPONENT: Result type: {type(result)}", file=sys.stderr)
        return result
    except Exception as e:
        print(f"❌ EXECUTE_COMPONENT: Method execution failed: {e}", file=sys.stderr)
        import traceback
        print(f"🔍 EXECUTE_COMPONENT: Method execution traceback:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise RuntimeError(f"Failed to execute {execution_method} on {component_type}: {e}") from e


# def _create_safe_langflow_environment() -> Dict[str, Any]:
#     """Create a safe execution environment with Langflow imports."""
#     exec_globals = {
#         '__builtins__': __builtins__,
#         'os': os,
#         'inspect': inspect,
#         'List': List,
#         'Dict': Dict,
#         'Any': Any,
#         'Optional': Optional,
#         'Union': Union,
#     }
    
#     # Try to import Langflow components dynamically
#     try:
#         from langflow.base.io.chat import ChatComponent
#         from langflow.inputs.inputs import BoolInput
#         from langflow.io import (
#             DropdownInput,
#             FileInput,
#             MessageTextInput,
#             MultilineInput,
#             Output,
#         )
#         from langflow.schema.message import Message
#         from langflow.schema.data import Data
#         from langflow.schema.dataframe import DataFrame
#         from langflow.custom.custom_component.component import Component
        
#         exec_globals.update({
#             'ChatComponent': ChatComponent,
#             'BoolInput': BoolInput,
#             'DropdownInput': DropdownInput,
#             'FileInput': FileInput,
#             'MessageTextInput': MessageTextInput,
#             'MultilineInput': MultilineInput,
#             'Output': Output,
#             'Message': Message,
#             'Data': Data,
#             'DataFrame': DataFrame,
#             'Component': Component,
#         })
#     except ImportError as e:
#         print(f"Warning: Could not import some Langflow components: {e}")
    
#     return exec_globals


def _find_component_class(exec_globals: Dict[str, Any], component_type: str):
    """Find the component class in the execution globals."""
    component_class = exec_globals.get(component_type)
    if component_class and isinstance(component_class, type):
        return component_class
    
    raise ValueError(f"Component class '{component_type}' not found in executed code")


def _determine_execution_method(outputs: List[Dict[str, Any]], selected_output: Optional[str]) -> str:
    """Determine which method to execute based on selected_output or outputs metadata."""
    
    print(f"🎯 DETERMINE_METHOD: Finding execution method", file=sys.stderr)
    print(f"🎯 DETERMINE_METHOD: Selected output: {selected_output}", file=sys.stderr)
    print(f"📤 DETERMINE_METHOD: Available outputs: {[o.get('name') for o in outputs]}", file=sys.stderr)
    
    # If selected_output is provided, try to find the corresponding method
    if selected_output:
        print(f"🔍 DETERMINE_METHOD: Looking for output named '{selected_output}'", file=sys.stderr)
        for i, output in enumerate(outputs):
            output_name = output.get('name')
            output_method = output.get('method')
            print(f"📤 DETERMINE_METHOD: Output {i}: name='{output_name}', method='{output_method}'", file=sys.stderr)
            
            if output_name == selected_output:
                if output_method:
                    print(f"✅ DETERMINE_METHOD: Found matching output, method: {output_method}", file=sys.stderr)
                    return output_method
                else:
                    print(f"⚠️  DETERMINE_METHOD: Found matching output but no method specified", file=sys.stderr)
        
        print(f"❌ DETERMINE_METHOD: selected_output '{selected_output}' not found in outputs", file=sys.stderr)
        raise ValueError(f"selected_output '{selected_output}' not found in outputs")
    else:
        print(f"❌ DETERMINE_METHOD: No selected_output provided", file=sys.stderr)
        raise ValueError("No selected_output provided")
    
    # # Fallback to first output's method
    # if not outputs:
    #     raise ValueError("No outputs metadata provided")
    
    # first_output = outputs[0]
    # method = first_output.get('method')
    
    # if not method:
    #     raise ValueError("No method specified in outputs metadata")
    
    # return method


# Removed manual attribute configuration - using Langflow's native set_attributes method

# Removed manual conversion functions - using native Langflow types throughout



if __name__ == "__main__":
    server.run()