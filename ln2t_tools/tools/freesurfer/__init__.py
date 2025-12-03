"""
FreeSurfer cortical reconstruction tool.

This module provides FreeSurfer integration for ln2t_tools, supporting
automatic T1w processing with optional T2w and FLAIR images.
"""

from .tool import FreeSurferTool

# Export the tool class for automatic discovery
TOOL_CLASS = FreeSurferTool

__all__ = ['FreeSurferTool', 'TOOL_CLASS']
