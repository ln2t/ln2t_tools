"""MRI to Print - MRI image export and printing tool."""

from .tool import Mri2PrintTool

# Required: export TOOL_CLASS for auto-discovery
TOOL_CLASS = Mri2PrintTool

__all__ = ['Mri2PrintTool', 'TOOL_CLASS']
