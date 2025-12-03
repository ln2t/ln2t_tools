"""
QSIPrep tool implementation.

QSIPrep is a preprocessing pipeline for diffusion MRI data that handles
motion correction, eddy current correction, distortion correction, and
resampling to a common resolution.
"""

import argparse
import logging
from pathlib import Path
from typing import List, Optional

from bids import BIDSLayout

from ln2t_tools.tools.base import BaseTool
from ln2t_tools.utils.defaults import DEFAULT_QSIPREP_VERSION

logger = logging.getLogger(__name__)


class QSIPrepTool(BaseTool):
    """QSIPrep diffusion MRI preprocessing tool.
    
    QSIPrep configures pipelines for processing diffusion-weighted MRI (dMRI)
    data. It handles preprocessing steps including motion correction, eddy
    current correction, susceptibility distortion correction, and resampling.
    """
    
    name = "qsiprep"
    help_text = "QSIPrep diffusion MRI preprocessing"
    description = """
QSIPrep Diffusion MRI Preprocessing

QSIPrep is a preprocessing pipeline for diffusion-weighted MRI data.
Key features include:

  - Motion and eddy current correction
  - Susceptibility distortion correction
  - Denoising (MP-PCA or patch2self)
  - Gibbs ringing removal
  - B1 field inhomogeneity correction
  - Resampling to specified resolution

The output is preprocessed DWI data ready for reconstruction with QSIRecon
or other downstream analysis tools.

Typical runtime: 4-8 hours per subject
"""
    default_version = DEFAULT_QSIPREP_VERSION
    requires_gpu = False
    
    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add QSIPrep-specific CLI arguments.
        
        Parameters
        ----------
        parser : argparse.ArgumentParser
            The subparser for this tool
        """
        parser.add_argument(
            "--output-resolution",
            type=float,
            required=True,
            help="Isotropic voxel size in mm for output (required)"
        )
        parser.add_argument(
            "--denoise-method",
            choices=["dwidenoise", "patch2self", "none"],
            default="dwidenoise",
            help="Denoising method (default: dwidenoise)"
        )
        parser.add_argument(
            "--dwi-only",
            action="store_true",
            help="Process only DWI data, ignore anatomical data"
        )
        parser.add_argument(
            "--anat-only",
            action="store_true",
            help="Process only anatomical data"
        )
        parser.add_argument(
            "--nprocs",
            type=int,
            default=8,
            help="Number of processes to use (default: 8)"
        )
        parser.add_argument(
            "--omp-nthreads",
            type=int,
            default=8,
            help="Number of OpenMP threads (default: 8)"
        )
    
    @classmethod
    def validate_args(cls, args: argparse.Namespace) -> bool:
        """Validate QSIPrep arguments.
        
        Parameters
        ----------
        args : argparse.Namespace
            Parsed command line arguments
            
        Returns
        -------
        bool
            True if arguments are valid
        """
        if not getattr(args, 'output_resolution', None):
            logger.error("--output-resolution is required for QSIPrep")
            return False
        return True
    
    @classmethod
    def check_requirements(
        cls,
        layout: BIDSLayout,
        participant_label: str,
        args: argparse.Namespace
    ) -> bool:
        """Check if DWI data exists for this participant.
        
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
        # Check for DWI data
        dwi_files = layout.get(
            subject=participant_label,
            scope="raw",
            suffix="dwi",
            extension=".nii.gz",
            return_type="filename"
        )
        
        if not dwi_files:
            logger.warning(f"No DWI data found for participant {participant_label}")
            return False
        
        # Check for anatomical data unless dwi-only is specified
        if not getattr(args, 'dwi_only', False):
            t1w_files = layout.get(
                subject=participant_label,
                scope="raw",
                suffix="T1w",
                extension=".nii.gz",
                return_type="filename"
            )
            
            if not t1w_files:
                logger.warning(f"No T1w images found for participant {participant_label}")
                if not getattr(args, 'anat_only', False):
                    logger.info("Consider using --dwi-only flag for DWI-only processing")
                    return False
        
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
        """Get QSIPrep output directory path.
        
        Parameters
        ----------
        dataset_derivatives : Path
            Base derivatives directory
        participant_label : str
            Participant ID (without 'sub-' prefix)
        args : argparse.Namespace
            Parsed command line arguments
        session : Optional[str]
            Session label (not used for QSIPrep)
        run : Optional[str]
            Run label (not used for QSIPrep)
            
        Returns
        -------
        Path
            Full path to output directory
        """
        version = args.version or cls.default_version
        output_label = args.output_label or f"qsiprep_{version}"
        
        return dataset_derivatives / output_label / f"sub-{participant_label}"
    
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
        """Build QSIPrep Apptainer command.
        
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
            Additional parameters
            
        Returns
        -------
        List[str]
            Command as list of strings
        """
        from ln2t_tools.utils.utils import build_apptainer_cmd
        
        version = args.version or cls.default_version
        output_label = args.output_label or f"qsiprep_{version}"
        output_dir = dataset_derivatives / output_label
        output_dir.mkdir(parents=True, exist_ok=True)
        
        cmd = build_apptainer_cmd(
            tool="qsiprep",
            fs_license=args.fs_license,
            rawdata=str(dataset_rawdata),
            derivatives=str(output_dir),
            participant_label=participant_label,
            apptainer_img=apptainer_img,
            output_resolution=getattr(args, 'output_resolution'),
            denoise_method=getattr(args, 'denoise_method', 'dwidenoise'),
            dwi_only="--dwi-only" if getattr(args, 'dwi_only', False) else "",
            anat_only="--anat-only" if getattr(args, 'anat_only', False) else "",
            nprocs=getattr(args, 'nprocs', 8),
            omp_nthreads=getattr(args, 'omp_nthreads', 8)
        )
        
        return [cmd] if isinstance(cmd, str) else cmd
    
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
        """Process a subject with QSIPrep.
        
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
            
        Returns
        -------
        bool
            True if processing succeeded
        """
        from ln2t_tools.utils.utils import launch_apptainer
        
        # Validate arguments
        if not cls.validate_args(args):
            return False
        
        # Check requirements
        if not cls.check_requirements(layout, participant_label, args):
            return False
        
        # Check if output already exists
        output_dir = cls.get_output_dir(dataset_derivatives, participant_label, args)
        if output_dir.exists():
            logger.info(f"Output exists, skipping: {output_dir}")
            return True
        
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
            cmd_str = cmd[0] if isinstance(cmd, list) and len(cmd) == 1 else ' '.join(cmd)
            launch_apptainer(cmd_str)
            return True
        except Exception as e:
            logger.error(f"Error processing {participant_label} with QSIPrep: {e}")
            return False
