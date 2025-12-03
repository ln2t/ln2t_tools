"""
QSIRecon diffusion MRI reconstruction tool.

This module provides QSIRecon integration for ln2t_tools, supporting
reconstruction and tractography from QSIPrep outputs.
"""

from .tool import QSIReconTool

# Export the tool class for automatic discovery
TOOL_CLASS = QSIReconTool

__all__ = ['QSIReconTool', 'TOOL_CLASS']
