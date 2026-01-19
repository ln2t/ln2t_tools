"""MRI to Print tool implementation."""

import argparse
import logging
from pathlib import Path
from typing import List, Optional

from bids import BIDSLayout

from ln2t_tools.tools.base import BaseTool
from ln2t_tools.utils.defaults import DEFAULT_MRI2PRINT_VERSION

logger = logging.getLogger(__name__)


class Mri2PrintTool(BaseTool):
    """MRI to Print - Convert FreeSurfer brain reconstructions to 3D-printable STL meshes.
    
    This tool processes FreeSurfer recon-all output and generates high-quality 3D mesh files
    suitable for 3D printing. It processes both cortical surfaces and subcortical structures,
    applies smoothing filters, and generates various output combinations.
    
    Requires FreeSurfer recon-all to have been run on the subject data first.
    """
    
    # Required class attributes
    name = "mri2print"
    help_text = "Convert FreeSurfer brain reconstructions to 3D-printable STL meshes"
    description = "MRI to Print - Create 3D-printable brain models from FreeSurfer output"
    default_version = DEFAULT_MRI2PRINT_VERSION
    requires_gpu = False
    
    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add tool-specific CLI arguments.
        
        Note: mri2print options should be passed via --tool-args.
        The --fs-version argument is handled as a common argument.
        """
        pass
    
    @classmethod
    def validate_args(cls, args: argparse.Namespace) -> bool:
        """Validate tool-specific arguments.
        
        FreeSurfer version is optional and will be auto-detected if not provided.
        """
        # No validation needed - fs-version is optional
        return True
    
    @classmethod
    def check_requirements(
        cls,
        layout: BIDSLayout,
        participant_label: str,
        args: argparse.Namespace
    ) -> bool:
        """Check if FreeSurfer outputs exist for this participant."""
        # Check for required FreeSurfer output files
        # This is a simplified check; in practice you'd check the actual FreeSurfer directory
        logger.info(
            f"mri2print requires FreeSurfer recon-all output. "
            f"Ensure 'freesurfer' tool has been run for participant {participant_label}"
        )
        return True
    
    @classmethod
    def get_output_dir(
        cls,
        dataset_derivatives: Path,
        participant_label: str,
        args: argparse.Namespace,
        session: Optional[str] = None,
        run: Optional[str] = None
    ) -> Path:
        """Get the output directory path for this participant."""
        version = args.version or cls.default_version
        logger.debug(f"get_output_dir: args.version={args.version}, cls.default_version={cls.default_version}, using version={version}")
        subdir = f"sub-{participant_label}"
        if session:
            subdir = f"{subdir}_ses-{session}"
        
        output_path = dataset_derivatives / f"{cls.name}_{version}" / subdir
        logger.debug(f"get_output_dir: output_path={output_path}")
        return output_path
    
    @classmethod
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
        
        mri2print processes FreeSurfer outputs and generates 3D-printable STL meshes.
        """
        version = args.version or cls.default_version
        logger.info(f"build_command: Using version {version}")
        output_dir = cls.get_output_dir(
            dataset_derivatives, participant_label, args
        )
        
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"build_command: Created output directory {output_dir}")
        
        # Find FreeSurfer output directory
        # User can specify a version with --fs-version, otherwise auto-detect
        fs_version = getattr(args, 'fs_version', None)
        
        if fs_version:
            # User specified a FreeSurfer version
            fs_dir_pattern = f"freesurfer_{fs_version}"
            logger.info(f"build_command: Looking for FreeSurfer version {fs_version}")
        else:
            # Auto-detect: look for any freesurfer_* directory
            fs_dir_pattern = "freesurfer_*"
            logger.info(f"build_command: Auto-detecting FreeSurfer version")
        
        # Search within the dataset_derivatives directory for freesurfer_* subdirectories
        fs_dirs = sorted(dataset_derivatives.glob(fs_dir_pattern))
        
        if not fs_dirs:
            logger.warning(
                f"No FreeSurfer output found in {dataset_derivatives} matching '{fs_dir_pattern}'. "
                f"Please run FreeSurfer first."
            )
            # Fallback to a reasonable default path
            if fs_version:
                fs_input_dir = dataset_derivatives / f"freesurfer_{fs_version}" / f"sub-{participant_label}"
            else:
                fs_input_dir = dataset_derivatives / "freesurfer" / f"sub-{participant_label}"
        else:
            # Use the most recent/last matching directory
            fs_input_dir = fs_dirs[-1] / f"sub-{participant_label}"
        
        logger.info(f"build_command: Using FreeSurfer input from {fs_input_dir}")
        
        # Build Apptainer command
        # Bind FreeSurfer input (read-only) and output directory
        cmd = [
            "apptainer", "run",
            "-B", f"{str(fs_input_dir)}:/freesurfer:ro",
            "-B", f"{str(output_dir)}:/output",
            str(apptainer_img),
            "-f", "/freesurfer",
            "-o", "/output",
            participant_label,
        ]
        
        # Tool-specific options should be passed via --tool-args
        # The mri2print container will handle them
        
        logger.info(f"build_command: Final command: {' '.join(cmd)}")
        return cmd
