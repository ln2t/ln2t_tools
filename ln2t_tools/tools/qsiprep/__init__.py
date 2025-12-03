"""
QSIPrep diffusion MRI preprocessing tool.

This module provides QSIPrep integration for ln2t_tools, supporting
preprocessing of diffusion MRI data.
"""

from .tool import QSIPrepTool

# Export the tool class for automatic discovery
TOOL_CLASS = QSIPrepTool

__all__ = ['QSIPrepTool', 'TOOL_CLASS']
