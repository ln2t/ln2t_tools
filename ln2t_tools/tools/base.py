"""
Base classes and interfaces for ln2t_tools processing tools.

This module defines the BaseTool abstract base class that all tools
must implement. It provides a consistent interface for:
- CLI argument registration
- Help text generation
- Subject processing
- HPC script generation
"""

import argparse
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Any, Type
from bids import BIDSLayout

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """Abstract base class for all processing tools.
    
    To create a new tool, inherit from this class and implement all
    abstract methods. Place your tool in ln2t_tools/tools/<toolname>/
    and ensure your __init__.py exports TOOL_CLASS pointing to your class.
    
    Example
    -------
    ```python
    # ln2t_tools/tools/mytool/__init__.py
    from .tool import MyTool
    TOOL_CLASS = MyTool
    ```
    
    Attributes
    ----------
    name : str
        Unique identifier for the tool (e.g., 'freesurfer', 'fmriprep')
    help_text : str
        Brief description shown in CLI help
    description : str
        Detailed description shown in tool-specific help
    default_version : str
        Default version to use if not specified
    requires_gpu : bool
        Whether the tool benefits from GPU acceleration
    """
    
    # Class attributes that should be overridden
    name: str = ""
    help_text: str = ""
    description: str = ""
    default_version: str = ""
    requires_gpu: bool = False
    
    @classmethod
    @abstractmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add tool-specific CLI arguments.
        
        This method is called during CLI setup to add tool-specific
        arguments to the subparser. Common arguments (--dataset, 
        --participant-label, etc.) are added automatically.
        
        Parameters
        ----------
        parser : argparse.ArgumentParser
            The subparser for this tool
            
        Example
        -------
        ```python
        @classmethod
        def add_arguments(cls, parser):
            parser.add_argument(
                "--my-option",
                default="value",
                help="Description of my option"
            )
        ```
        """
        pass
    
    @classmethod
    @abstractmethod
    def validate_args(cls, args: argparse.Namespace) -> bool:
        """Validate tool-specific arguments.
        
        Called after argument parsing to validate that all required
        options are set correctly for this tool.
        
        Parameters
        ----------
        args : argparse.Namespace
            Parsed command line arguments
            
        Returns
        -------
        bool
            True if arguments are valid, False otherwise
        """
        pass
    
    @classmethod
    @abstractmethod
    def check_requirements(
        cls,
        layout: BIDSLayout,
        participant_label: str,
        args: argparse.Namespace
    ) -> bool:
        """Check if requirements are met to process this participant.
        
        Verify that all required input files exist and any prerequisites
        (e.g., FreeSurfer output for fMRIPrep) are available.
        
        Parameters
        ----------
        layout : BIDSLayout
            BIDS dataset layout
        participant_label : str
            Participant ID (without 'sub-' prefix)
        args : argparse.Namespace
            Parsed command line arguments
            
        Returns
        -------
        bool
            True if requirements are met
        """
        pass
    
    @classmethod
    @abstractmethod
    def get_output_dir(
        cls,
        dataset_derivatives: Path,
        participant_label: str,
        args: argparse.Namespace,
        session: Optional[str] = None,
        run: Optional[str] = None
    ) -> Path:
        """Get the output directory path for this participant.
        
        Parameters
        ----------
        dataset_derivatives : Path
            Base derivatives directory
        participant_label : str
            Participant ID (without 'sub-' prefix)
        args : argparse.Namespace
            Parsed command line arguments
        session : Optional[str]
            Session label (without 'ses-' prefix)
        run : Optional[str]
            Run label
            
        Returns
        -------
        Path
            Full path to output directory
        """
        pass
    
    @classmethod
    @abstractmethod
    def build_command(
        cls,
        layout: BIDSLayout,
        participant_label: str,
        args: argparse.Namespace,
        dataset_rawdata: Path,
        dataset_derivatives: Path,
        apptainer_img: str,
        **kwargs
    ) -> List[str]:
        """Build the Apptainer command to run the tool.
        
        Parameters
        ----------
        layout : BIDSLayout
            BIDS dataset layout
        participant_label : str
            Participant ID (without 'sub-' prefix)
        args : argparse.Namespace
            Parsed command line arguments
        dataset_rawdata : Path
            Path to BIDS rawdata directory
        dataset_derivatives : Path
            Path to derivatives directory
        apptainer_img : str
            Path to Apptainer image
        **kwargs : dict
            Additional tool-specific parameters
            
        Returns
        -------
        List[str]
            Command as list of strings
        """
        pass
    
    @classmethod
    def process_subject(
        cls,
        layout: BIDSLayout,
        participant_label: str,
        args: argparse.Namespace,
        dataset_rawdata: Path,
        dataset_derivatives: Path,
        apptainer_img: str,
        **kwargs
    ) -> bool:
        """Process a single subject with this tool.
        
        This is the main entry point for processing. The default
        implementation checks requirements, builds the command, and
        launches it. Override for custom processing logic.
        
        Parameters
        ----------
        layout : BIDSLayout
            BIDS dataset layout
        participant_label : str
            Participant ID (without 'sub-' prefix)
        args : argparse.Namespace
            Parsed command line arguments
        dataset_rawdata : Path
            Path to BIDS rawdata directory
        dataset_derivatives : Path
            Path to derivatives directory
        apptainer_img : str
            Path to Apptainer image
        **kwargs : dict
            Additional tool-specific parameters
            
        Returns
        -------
        bool
            True if processing succeeded
        """
        from ln2t_tools.utils.utils import launch_apptainer
        
        # Check requirements
        if not cls.check_requirements(layout, participant_label, args):
            logger.warning(f"Requirements not met for {participant_label} with {cls.name}")
            return False
        
        # Build command
        cmd = cls.build_command(
            layout=layout,
            participant_label=participant_label,
            args=args,
            dataset_rawdata=dataset_rawdata,
            dataset_derivatives=dataset_derivatives,
            apptainer_img=apptainer_img,
            **kwargs
        )
        
        if not cmd:
            logger.error(f"Failed to build command for {participant_label}")
            return False
        
        # Launch
        try:
            # Join command list into string
            cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
            launch_apptainer(cmd_str)
            return True
        except Exception as e:
            logger.error(f"Error processing {participant_label} with {cls.name}: {e}")
            return False
    
    @classmethod
    def generate_hpc_script(
        cls,
        participant_label: str,
        dataset: str,
        args: argparse.Namespace,
        **kwargs
    ) -> str:
        """Generate HPC batch script for this tool.
        
        Override this method to customize the HPC script generation.
        The default implementation uses the generic HPC script generator.
        
        Parameters
        ----------
        participant_label : str
            Participant ID (without 'sub-' prefix)
        dataset : str
            Dataset name
        args : argparse.Namespace
            Parsed command line arguments
            
        Returns
        -------
        str
            Complete batch script content
        """
        from ln2t_tools.utils.hpc import generate_hpc_script
        return generate_hpc_script(
            tool=cls.name,
            participant_label=participant_label,
            dataset=dataset,
            args=args,
            **kwargs
        )


class ToolRegistry:
    """Registry for managing available processing tools.
    
    This class maintains a mapping of tool names to their implementations
    and provides methods for tool discovery and registration.
    
    Attributes
    ----------
    _tools : Dict[str, Type[BaseTool]]
        Mapping of tool names to their classes
    """
    
    def __init__(self):
        self._tools: Dict[str, Type[BaseTool]] = {}
    
    def register(self, tool_class: Type[BaseTool]) -> None:
        """Register a tool class.
        
        Parameters
        ----------
        tool_class : Type[BaseTool]
            The tool class to register
            
        Raises
        ------
        ValueError
            If the tool name is already registered
        """
        if not tool_class.name:
            raise ValueError(f"Tool class {tool_class.__name__} has no name defined")
        
        if tool_class.name in self._tools:
            logger.warning(f"Tool '{tool_class.name}' already registered, overwriting")
        
        self._tools[tool_class.name] = tool_class
        logger.debug(f"Registered tool: {tool_class.name}")
    
    def get(self, name: str) -> Optional[Type[BaseTool]]:
        """Get a tool class by name.
        
        Parameters
        ----------
        name : str
            Tool name
            
        Returns
        -------
        Optional[Type[BaseTool]]
            The tool class, or None if not found
        """
        return self._tools.get(name)
    
    def get_all(self) -> Dict[str, Type[BaseTool]]:
        """Get all registered tools.
        
        Returns
        -------
        Dict[str, Type[BaseTool]]
            Dictionary mapping tool names to tool classes
        """
        return dict(self._tools)
    
    def list_tools(self) -> List[str]:
        """Get list of registered tool names.
        
        Returns
        -------
        List[str]
            Sorted list of tool names
        """
        return sorted(self._tools.keys())
    
    def items(self):
        """Iterate over registered tools.
        
        Yields
        ------
        Tuple[str, Type[BaseTool]]
            Tool name and class pairs
        """
        return self._tools.items()
    
    def __contains__(self, name: str) -> bool:
        return name in self._tools
    
    def __len__(self) -> int:
        return len(self._tools)
