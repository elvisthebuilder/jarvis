"""Tool registry — central registration and dispatch for all Jarvis tools.

Each tool is a Python function with type hints and a clear docstring.
The registry auto-generates the JSON schema that Gemma 4 and Gemini use
to decide when and how to call each tool.
"""

import inspect
import logging
from typing import Callable, Any, get_type_hints

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for all Jarvis tools.
    
    Tools are registered with their function reference, and the registry
    automatically generates JSON schemas for the LLM's function calling interface.
    """

    def __init__(self):
        self._tools: dict[str, Callable] = {}
        self._schemas: list[dict] = []

    def register(self, func: Callable) -> Callable:
        """Register a tool function. Can be used as a decorator.
        
        The function must have:
        - A clear, descriptive docstring (used by the LLM to decide when to call it)
        - Type hints for all parameters
        
        Example:
            @registry.register
            def play_spotify(query: str) -> str:
                \"""Play a song, artist, playlist, or mood on Spotify.\"""
                ...
        """
        name = func.__name__
        if name in self._tools:
            logger.warning(f"Tool '{name}' already registered, overwriting")

        self._tools[name] = func
        schema = self._generate_schema(func)
        
        # Replace existing schema or append
        self._schemas = [s for s in self._schemas if s["function"]["name"] != name]
        self._schemas.append(schema)
        
        logger.debug(f"Registered tool: {name}")
        return func

    def get_tool(self, name: str) -> Callable | None:
        """Get a tool function by name."""
        return self._tools.get(name)

    async def execute(self, name: str, arguments: dict) -> str:
        """Execute a tool by name with the given arguments.
        
        Args:
            name: The tool function name
            arguments: Dict of keyword arguments
            
        Returns:
            String result of the tool execution
        """
        func = self._tools.get(name)
        if not func:
            return f"Error: Unknown tool '{name}'"

        try:
            logger.info(f"Executing tool: {name}({arguments})")
            
            # Support both sync and async tools
            if inspect.iscoroutinefunction(func):
                result = await func(**arguments)
            else:
                result = func(**arguments)

            logger.info(f"Tool {name} result: {result[:200] if isinstance(result, str) else result}")
            return str(result)

        except Exception as e:
            error_msg = f"Tool '{name}' failed: {type(e).__name__}: {e}"
            logger.error(error_msg)
            return error_msg

    def get_schemas(self) -> list[dict]:
        """Get all tool schemas for the LLM API.
        
        Returns:
            List of tool definition dicts in OpenAI/Ollama format.
        """
        return self._schemas

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def _generate_schema(self, func: Callable) -> dict:
        """Auto-generate a JSON tool schema from a function's signature and docstring."""
        hints = get_type_hints(func)
        sig = inspect.signature(func)
        
        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue

            param_type = hints.get(param_name, str)
            json_type = self._python_type_to_json(param_type)
            
            prop = {"type": json_type}
            
            # Extract parameter description from docstring if available
            param_desc = self._extract_param_doc(func.__doc__ or "", param_name)
            if param_desc:
                prop["description"] = param_desc

            properties[param_name] = prop

            # If no default value, it's required
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        schema = {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": (func.__doc__ or "").strip().split("\n")[0],
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

        return schema

    @staticmethod
    def _python_type_to_json(python_type) -> str:
        """Convert a Python type hint to a JSON schema type string."""
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }
        # Handle Optional, Union, etc.
        origin = getattr(python_type, "__origin__", None)
        if origin is not None:
            python_type = origin
        return type_map.get(python_type, "string")

    @staticmethod
    def _extract_param_doc(docstring: str, param_name: str) -> str | None:
        """Extract a parameter description from a docstring."""
        for line in docstring.split("\n"):
            line = line.strip()
            if line.startswith(f"{param_name}:") or line.startswith(f"{param_name} "):
                _, _, desc = line.partition(":")
                return desc.strip() if desc.strip() else None
        return None


# Global registry instance — tools import this and register themselves
registry = ToolRegistry()
