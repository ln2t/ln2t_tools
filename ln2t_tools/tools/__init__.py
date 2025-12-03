"""
Tool registry and base classes for ln2t_tools.

This module provides the infrastructure for registering and discovering
processing tools. Each tool should be placed in its own subdirectory
under tools/ and implement the BaseTool interface.

To add a new tool:
1. Create a new directory under tools/ (e.g., tools/mytool/)
2. Create an __init__.py that exports a class inheriting from BaseTool
3. Implement all required methods (see BaseTool docstring)
4. The tool will be automatically discovered and registered

See docs/adding_tools.md for detailed instructions.
"""

from .base import BaseTool, ToolRegistry

# Global tool registry instance
registry = ToolRegistry()


def discover_tools():
    """Discover and register all tools from the tools/ directory."""
    import importlib
    import pkgutil
    from pathlib import Path
    
    tools_dir = Path(__file__).parent
    
    for _, module_name, is_pkg in pkgutil.iter_modules([str(tools_dir)]):
        if is_pkg and module_name not in ('base', '__pycache__'):
            try:
                module = importlib.import_module(f'.{module_name}', package='ln2t_tools.tools')
                # Look for a tool class in the module
                if hasattr(module, 'TOOL_CLASS'):
                    tool_class = module.TOOL_CLASS
                    registry.register(tool_class)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to load tool '{module_name}': {e}")


# Convenience functions for external access
def auto_discover_tools():
    """Auto-discover and register all tools.
    
    Note: Tools are automatically discovered on module import.
    This function can be called to re-discover tools if needed.
    """
    # Only discover if not already done
    if not registry._tools:
        discover_tools()


def get_all_tools():
    """Get all registered tools.
    
    Returns:
        Dict[str, Type[BaseTool]]: Dictionary mapping tool names to tool classes
    """
    return registry.get_all()


def get_tool(name: str):
    """Get a specific tool by name.
    
    Args:
        name: The tool name (e.g., 'freesurfer', 'fmriprep')
        
    Returns:
        Type[BaseTool]: The tool class, or None if not found
    """
    return registry.get(name)


def register_tool(tool_class):
    """Decorator to register a tool class.
    
    Args:
        tool_class: A class inheriting from BaseTool
        
    Returns:
        The tool class (unchanged)
    """
    registry.register(tool_class)
    return tool_class


# Discover tools on import
discover_tools()

__all__ = [
    'BaseTool', 
    'ToolRegistry', 
    'registry', 
    'discover_tools',
    'auto_discover_tools',
    'get_all_tools',
    'get_tool',
    'register_tool'
]
