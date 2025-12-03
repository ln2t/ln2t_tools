"""
MELD Graph lesion detection tool.

This module provides MELD Graph integration for ln2t_tools, supporting
automated detection of focal cortical dysplasia from FreeSurfer outputs.
"""

from .tool import MELDGraphTool

# Export the tool class for automatic discovery
TOOL_CLASS = MELDGraphTool

__all__ = ['MELDGraphTool', 'TOOL_CLASS']
