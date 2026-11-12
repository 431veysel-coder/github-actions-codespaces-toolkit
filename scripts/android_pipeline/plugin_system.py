#!/usr/bin/env python3
"""
Plugin System for MCP Tools
Decorator-based tool registration with auto-discovery and hot-reload capability.
"""

import importlib
import importlib.util
import inspect
import logging
import os
import sys
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass
class ToolMetadata:
    """Metadata for a registered tool"""

    name: str
    description: str
    func: Callable
    params: Dict[str, Any] = field(default_factory=dict)
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    deprecated: bool = False


class ToolPlugin(Protocol):
    """Protocol for tool plugins"""

    name: str
    description: str

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]: ...


class PluginRegistry:
    """Registry for MCP tool plugins"""

    def __init__(self):
        self._tools: Dict[str, ToolMetadata] = {}
        self._categories: Dict[str, List[str]] = {}

    def register(self, metadata: ToolMetadata) -> None:
        """Register a tool"""
        if metadata.name in self._tools:
            logger.warning(f"Tool '{metadata.name}' already registered, overwriting")

        self._tools[metadata.name] = metadata

        if metadata.category not in self._categories:
            self._categories[metadata.category] = []
        if metadata.name not in self._categories[metadata.category]:
            self._categories[metadata.category].append(metadata.name)

        logger.debug(f"Registered tool: {metadata.name} ({metadata.category})")

    def unregister(self, name: str) -> bool:
        """Unregister a tool"""
        if name in self._tools:
            metadata = self._tools.pop(name)
            if metadata.category in self._categories:
                self._categories[metadata.category].remove(name)
            return True
        return False

    def get(self, name: str) -> Optional[ToolMetadata]:
        """Get tool metadata by name"""
        return self._tools.get(name)

    def list_tools(self, category: str = None) -> List[ToolMetadata]:
        """List all tools, optionally filtered by category"""
        if category:
            return [self._tools[name] for name in self._categories.get(category, [])]
        return list(self._tools.values())

    def get_categories(self) -> Dict[str, List[str]]:
        """Get all categories and their tools"""
        return {k: v[:] for k, v in self._categories.items()}

    def get_tool_names(self) -> List[str]:
        """Get all tool names"""
        return list(self._tools.keys())


# Global registry instance
registry = PluginRegistry()


def tool(
    name: str = None,
    description: str = "",
    category: str = "general",
    tags: List[str] = None,
    version: str = "1.0.0",
    deprecated: bool = False,
    params: Dict[str, Any] = None,
):
    """
    Decorator to register a function as an MCP tool.

    Usage:
        @tool(name="my_tool", description="Does something", category="android")
        def my_tool(param1: str, param2: int = 5) -> Dict[str, Any]:
            return {"result": f"{param1}: {param2}"}
    """

    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        tool_desc = description or func.__doc__ or f"Tool: {tool_name}"
        tool_tags = tags or []
        tool_params = params or {}

        # Extract parameter info from function signature
        sig = inspect.signature(func)
        for param_name, param in sig.parameters.items():
            if param_name not in tool_params:
                param_info = {"type": "string", "description": f"Parameter: {param_name}"}
                if param.annotation != inspect.Parameter.empty:
                    param_info["type"] = _type_to_json_schema(param.annotation)
                if param.default != inspect.Parameter.empty:
                    param_info["default"] = param.default
                tool_params[param_name] = param_info

        metadata = ToolMetadata(
            name=tool_name,
            description=tool_desc,
            func=func,
            params=tool_params,
            category=category,
            tags=tool_tags,
            version=version,
            deprecated=deprecated,
        )

        registry.register(metadata)

        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Attach metadata to wrapper for introspection
        wrapper._tool_metadata = metadata
        return wrapper

    return decorator


def _type_to_json_schema(py_type: Any) -> str:
    """Convert Python type to JSON schema type"""
    if py_type == str:
        return "string"
    elif py_type == int:
        return "integer"
    elif py_type == float:
        return "number"
    elif py_type == bool:
        return "boolean"
    elif py_type == list or py_type == List:
        return "array"
    elif py_type == dict or py_type == Dict:
        return "object"
    else:
        return "string"


class PluginLoader:
    """Load plugins from directories or entry points"""

    def __init__(self, registry: PluginRegistry = None):
        self.registry = registry or PluginRegistry()
        self._loaded_modules: Dict[str, Any] = {}

    def load_from_directory(self, directory: str, pattern: str = "*.py") -> int:
        """Load plugins from a directory"""
        count = 0
        dir_path = Path(directory).resolve()

        if not dir_path.exists():
            logger.warning(f"Plugin directory not found: {directory}")
            return 0

        # Add directory to sys.path if not already
        str_path = str(dir_path.parent)
        if str_path not in sys.path:
            sys.path.insert(0, str_path)

        for py_file in dir_path.glob(pattern):
            if py_file.name.startswith("_"):
                continue

            module_name = py_file.stem
            try:
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    self._loaded_modules[module_name] = module
                    count += 1
                    logger.debug(f"Loaded plugin module: {module_name}")
            except Exception as e:
                logger.error(f"Failed to load plugin {module_name}: {e}")

        return count

    def load_from_entry_points(self, group: str = "minis.tools") -> int:
        """Load plugins from entry points (setuptools)"""
        count = 0
        try:
            for entry_point in importlib.metadata.entry_points(group=group):
                try:
                    plugin = entry_point.load()
                    if callable(plugin):
                        plugin(self.registry)
                    count += 1
                    logger.debug(f"Loaded entry point: {entry_point.name}")
                except Exception as e:
                    logger.error(f"Failed to load entry point {entry_point.name}: {e}")
        except Exception as e:
            logger.debug(f"Entry point loading not available: {e}")
        return count

    def load_package(self, package_name: str) -> int:
        """Load all modules from a package"""
        count = 0
        try:
            package = importlib.import_module(package_name)
            package_path = Path(package.__file__).parent

            for py_file in package_path.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue
                module_name = f"{package_name}.{py_file.stem}"
                try:
                    importlib.import_module(module_name)
                    count += 1
                except Exception as e:
                    logger.debug(f"Skipping {module_name}: {e}")
        except Exception as e:
            logger.error(f"Failed to load package {package_name}: {e}")
        return count

    def reload_all(self) -> int:
        """Hot-reload all loaded modules"""
        count = 0
        for name, module in self._loaded_modules.items():
            try:
                importlib.reload(module)
                count += 1
                logger.debug(f"Reloaded module: {name}")
            except Exception as e:
                logger.error(f"Failed to reload {name}: {e}")
        return count

    def get_loaded_modules(self) -> Dict[str, Any]:
        return self._loaded_modules.copy()


def create_tool_adapter(metadata: ToolMetadata) -> Callable:
    """Create an MCP-compatible tool function from metadata"""

    async def async_wrapper(**kwargs) -> str:
        try:
            # Validate required parameters
            for param_name, param_info in metadata.params.items():
                if param_info.get("required", False) and param_name not in kwargs:
                    raise ValueError(f"Missing required parameter: {param_name}")

            # Call the function
            if inspect.iscoroutinefunction(metadata.func):
                result = await metadata.func(**kwargs)
            else:
                result = metadata.func(**kwargs)

            # Ensure result is JSON serializable
            import json

            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            logger.error(f"Tool {metadata.name} error: {e}")
            import json

            return json.dumps({"error": str(e), "tool": metadata.name})

    # Set function metadata for MCP
    async_wrapper.__name__ = metadata.name
    async_wrapper.__doc__ = metadata.description
    async_wrapper._tool_metadata = metadata

    return async_wrapper


def register_all_tools(mcp_app, loader: PluginLoader = None) -> int:
    """Register all tools from registry to MCP app"""
    if loader:
        loader.load_from_entry_points()

    count = 0
    for metadata in registry.list_tools():
        try:
            adapter = create_tool_adapter(metadata)
            mcp_app.add_tool(adapter)
            count += 1
        except Exception as e:
            logger.error(f"Failed to register tool {metadata.name}: {e}")

    return count


# Example usage
if __name__ == "__main__":
    # Test the plugin system
    @tool(name="example_tool", description="An example tool", category="test")
    def example_tool(message: str, count: int = 1) -> Dict[str, Any]:
        """Repeat a message"""
        return {"result": message * count}

    @tool(name="another_tool", description="Another tool", category="test", tags=["demo"])
    def another_tool(value: float) -> Dict[str, Any]:
        return {"doubled": value * 2}

    # List registered tools
    print("Registered tools:")
    for meta in registry.list_tools():
        print(f"  - {meta.name}: {meta.description} ({meta.category})")

    print("\nCategories:")
    for cat, tools in registry.get_categories().items():
        print(f"  {cat}: {tools}")

    # Test tool execution
    import asyncio

    async def test():
        result = await create_tool_adapter(registry.get("example_tool"))(message="Hello ", count=3)
        print(f"\nTool result: {result}")

    asyncio.run(test())
    print("\nPlugin system test passed!")
