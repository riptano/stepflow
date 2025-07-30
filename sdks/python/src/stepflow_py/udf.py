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
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

import inspect
import sys
from typing import Any

import msgspec

from stepflow_py.context import StepflowContext
from stepflow_py.exceptions import StepflowValueError

# Global cache for compiled functions by blob_id
_function_cache: dict[str, Any] = {}


class UdfInput(msgspec.Struct):
    blob_id: str
    input: dict


async def udf(input: UdfInput, context: StepflowContext) -> Any:
    """Execute user-defined function (UDF) using cached compiled functions from blobs.

    Args:
        input: Contains blob_id (referencing stored code/schema) and input (data)

    Returns:
        The result of the UDF execution.
    """
    # Check if we have a cached function for this blob_id
    if input.blob_id in _function_cache:
        print(f"Using cached function for blob_id: {input.blob_id}", file=sys.stderr)
        compiled_func = _function_cache[input.blob_id]["function"]
    else:
        print(
            f"Loading and compiling function for blob_id: {input.blob_id}",
            file=sys.stderr,
        )

        # Get the blob containing the function definition
        try:
            blob_data = await context.get_blob(input.blob_id)
        except Exception as e:
            raise ValueError(f"Failed to retrieve blob {input.blob_id}: {e}") from e

        # Extract code and schema from blob
        if not isinstance(blob_data, dict):
            raise ValueError(f"Blob {input.blob_id} must contain a dictionary")

        code = blob_data.get("code")
        input_schema = blob_data.get("input_schema")
        function_name = blob_data.get("function_name")

        if not code:
            raise ValueError(f"Blob {input.blob_id} must contain 'code' field")
        if not input_schema:
            raise ValueError(f"Blob {input.blob_id} must contain 'input_schema' field")

        # Compile the function with validation built-in
        compiled_func = _compile_function(code, function_name, input_schema)

        # Cache the compiled function
        _function_cache[input.blob_id] = {
            "function": compiled_func,
            "input_schema": input_schema,
            "function_name": function_name,
        }

    # Execute the cached function (validation happens inside)
    try:
        result = await compiled_func(input.input, context)
    except Exception as e:
        raise ValueError(f"Function execution failed: {e}") from e

    print(f"Result: {result}", file=sys.stderr)
    return result


class _InputWrapper(dict):
    def __init__(self, input_data: dict, path: list[str] | None = None):
        super().__init__(input_data)
        self.path = path or []

    def __getattr__(self, item):
        """Allow attribute access to input data."""
        return self[item]

    def __getitem__(self, item):
        """Allow dictionary-like access to input data."""
        if item in self:
            value = super().__getitem__(item)
            if isinstance(value, dict):
                return _InputWrapper(value, self.path + [item])
            else:
                return value
        raise StepflowValueError(f"Input has no attribute '{item}'")


def _compile_function(code: str, function_name: str | None, input_schema: dict):
    """Compile a function from code string and return the callable with validation."""
    import json

    import jsonschema

    # Create a safe execution environment
    safe_globals = {
        "__builtins__": {
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "range": range,
            "sum": sum,
            "min": min,
            "max": max,
            "abs": abs,
            "round": round,
            "sorted": sorted,
            "reversed": reversed,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "any": any,
            "all": all,
            "print": print,
            "isinstance": isinstance,
            "__import__": __import__,
            "getattr": getattr,
        },
        "json": json,
        "math": __import__("math"),
        "re": __import__("re"),
    }

    def validate_input(data):
        """Validate input data against the schema."""
        try:
            jsonschema.validate(data, input_schema)
        except jsonschema.ValidationError as e:
            raise ValueError(f"Input validation failed: {e.message}") from e
        except jsonschema.SchemaError as e:
            raise ValueError(f"Invalid schema: {e.message}") from e

    if function_name is not None:
        # Code contains function definition(s)
        local_scope: dict[str, Any] = {}
        try:
            exec(code, safe_globals, local_scope)
        except Exception as e:
            raise ValueError(f"Code execution failed: {e}") from e

        # Look for the specified function
        if function_name not in local_scope:
            raise ValueError(f"Function '{function_name}' not found in code")

        func = local_scope[function_name]
        if not callable(func):
            raise ValueError(f"'{function_name}' is not a function")

        sig = inspect.signature(func)
        params = list(sig.parameters)

        input_annotation = sig.parameters[params[0]].annotation
        wrap_input = (
            input_annotation == inspect.Parameter.empty or input_annotation is dict
        )
        use_context = len(params) == 2 and params[1] == "context"

        match (inspect.iscoroutinefunction(func), wrap_input, use_context):
            case (True, True, True):

                async def wrapper(input_data, context):
                    validate_input(input_data)
                    return await func(_InputWrapper(input_data), context)

                return wrapper
            case (True, True, False):

                async def wrapper(input_data, context):
                    validate_input(input_data)
                    return await func(_InputWrapper(input_data))

                return wrapper
            case (True, False, True):

                async def wrapper(input_data, context):
                    validate_input(input_data)
                    return await func(input_data, context)

                return wrapper
            case (True, False, False):

                async def wrapper(input_data, context):
                    validate_input(input_data)
                    return await func(input_data)

                return wrapper
            case (False, True, True):

                async def wrapper(input_data, context):
                    validate_input(input_data)
                    return func(_InputWrapper(input_data), context)

                return wrapper
            case (False, True, False):

                async def wrapper(input_data, context):
                    validate_input(input_data)
                    return func(_InputWrapper(input_data))

                return wrapper
            case (False, False, True):

                async def wrapper(input_data, context):
                    validate_input(input_data)
                    return func(input_data, context)

                return wrapper
            case (False, False, False):

                async def wrapper(input_data, context):
                    validate_input(input_data)
                    return func(input_data)

                return wrapper
    else:
        # Code is a function body - wrap it appropriately
        try:
            # Try as expression first (for simple cases)
            wrapped_code = f"lambda input: {code}"
            func = eval(wrapped_code, safe_globals)

            async def wrapper(input_data, context):
                validate_input(input_data)
                return func(_InputWrapper(input_data))

            return wrapper
        except Exception:
            # If that fails, try as statements in a function body
            try:
                # Properly indent each line of the code
                indented_lines = []
                for line in code.split("\n"):
                    if line.strip():  # Only indent non-empty lines
                        indented_lines.append("    " + line)
                    else:
                        indented_lines.append("")  # Keep empty lines as-is

                func_code = f"""def _temp_func(input, context):
{chr(10).join(indented_lines)}"""
                local_scope = {}
                exec(func_code, safe_globals, local_scope)
                temp_func = local_scope["_temp_func"]

                # Wrap to always pass context and validate
                async def wrapper(input_data, context):
                    validate_input(input_data)
                    return temp_func(_InputWrapper(input_data), context)

                return wrapper
            except Exception as e:
                raise ValueError(f"Code compilation failed: {e}") from e
