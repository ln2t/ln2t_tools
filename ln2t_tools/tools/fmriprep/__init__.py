"""
fMRIPrep functional MRI preprocessing tool.

This module provides fMRIPrep integration for ln2t_tools, supporting
automatic preprocessing of functional MRI data with optional FreeSurfer
surface reconstruction.
"""

from .tool import FMRIPrepTool

# Export the tool class for automatic discovery
TOOL_CLASS = FMRIPrepTool

__all__ = ['FMRIPrepTool', 'TOOL_CLASS']
