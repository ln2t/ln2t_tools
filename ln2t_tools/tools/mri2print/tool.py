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
        """Add tool-specific CLI arguments."""
        parser.add_argument(
            "--decimation",
            type=int,
            default=10000000000,
            help="Target face count for mesh decimation (default: 10000000000 - no decimation)"
        )
        parser.add_argument(
            "--skip-cortex",
            action="store_true",
            help="Skip cortical surface processing"
        )
        parser.add_argument(
            "--skip-subcortex",
            action="store_true",
            help="Skip subcortical structure processing"
        )
        parser.add_argument(
            "--no-compress",
            action="store_true",
            help="Don't gzip the output STL files"
        )
        parser.add_argument(
            "--cortex-iterations",
            type=int,
            default=70,
            help="Cortex smoothing iterations (default: 70)"
        )
        parser.add_argument(
            "--subcortex-iterations",
            type=int,
            default=10,
            help="Subcortex smoothing iterations (default: 10)"
        )
    
    @classmethod
    def validate_args(cls, args: argparse.Namespace) -> bool:
        """Validate tool-specific arguments."""
        if getattr(args, 'decimation', None) is not None:
            if getattr(args, 'decimation', 0) < 0:
                logger.error("--decimation must be a positive integer")
                return False
        
        cortex_iter = getattr(args, 'cortex_iterations', None)
        if cortex_iter is not None and cortex_iter < 0:
            logger.error("--cortex-iterations must be a positive integer")
            return False
        
        subcortex_iter = getattr(args, 'subcortex_iterations', None)
        if subcortex_iter is not None and subcortex_iter < 0:
            logger.error("--subcortex-iterations must be a positive integer")
            return False
        
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
        subdir = f"sub-{participant_label}"
        if session:
            subdir = f"{subdir}_ses-{session}"
        
        return dataset_derivatives / f"{cls.name}_{version}" / subdir
    
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
        output_dir = cls.get_output_dir(
            dataset_derivatives, participant_label, args
        )
        
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Find FreeSurfer output directory (typically freesurfer_*/sub-*)
        # Look for the most recent/common FreeSurfer version
        fs_parent = dataset_derivatives.parent
        fs_dirs = sorted(fs_parent.glob("*freesurfer*"))
        
        if not fs_dirs:
            logger.warning(
                f"No FreeSurfer output found in {fs_parent}. "
                f"Please run FreeSurfer first."
            )
            fs_input = f"{dataset_derivatives}/freesurfer/sub-{participant_label}"
        else:
            fs_input = fs_dirs[-1] / f"sub-{participant_label}"
        
        # Build Apptainer command
        # Bind FreeSurfer input (read-only) and output directory
        cmd = [
            "apptainer", "run",
            "-B", f"{str(fs_input)}:/freesurfer:ro",
            "-B", f"{str(output_dir)}:/output",
            apptainer_img,
            "-f", "/freesurfer",
            "-o", "/output",
            participant_label,
        ]
        
        # Add tool-specific options
        decimation = getattr(args, 'decimation', 10000000000)
        if decimation != 10000000000:
            cmd.extend(["--decimation", str(decimation)])
        
        if getattr(args, 'skip_cortex', False):
            cmd.append("--skip-cortex")
        
        if getattr(args, 'skip_subcortex', False):
            cmd.append("--skip-subcortex")
        
        if getattr(args, 'no_compress', False):
            cmd.append("--no-compress")
        
        cortex_iter = getattr(args, 'cortex_iterations', 70)
        if cortex_iter != 70:
            cmd.extend(["--cortex-iterations", str(cortex_iter)])
        
        subcortex_iter = getattr(args, 'subcortex_iterations', 10)
        if subcortex_iter != 10:
            cmd.extend(["--subcortex-iterations", str(subcortex_iter)])
        
        return cmd
    
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
    ) -> int:
        """Process a single participant.
        
        Returns exit code (0 for success, non-zero for failure).
        """
        logger.info(f"Processing participant {participant_label} with mri2print")
        
        # Build and execute the command
        cmd = cls.build_command(
            layout=layout,
            participant_label=participant_label,
            args=args,
            dataset_rawdata=dataset_rawdata,
            dataset_derivatives=dataset_derivatives,
            apptainer_img=apptainer_img,
            **kwargs
        )
        
        # Import here to avoid circular imports
        from ln2t_tools.utils.utils import launch_apptainer
        
        cmd_str = " ".join(cmd)
        return launch_apptainer(cmd_str)
