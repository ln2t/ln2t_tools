"""SLURM HPC cluster job submission utilities."""

import logging
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, Any
import tempfile

logger = logging.getLogger(__name__)

# HPC Configuration
HPC_HOST = "lyra.ulb.be"
HPC_USER = "arovai"
HPC_ADDRESS = f"{HPC_USER}@{HPC_HOST}"


def validate_slurm_config(args) -> None:
    """Validate SLURM configuration arguments."""
    if args.slurm:
        required_args = {
            '--slurm-rawdata': args.slurm_rawdata,
            '--slurm-derivatives': args.slurm_derivatives,
            '--slurm-apptainer-dir': args.slurm_apptainer_dir,
        }
        
        missing = [arg for arg, value in required_args.items() if not value]
        if missing:
            raise ValueError(
                f"When using --slurm, you must provide: {', '.join(missing)}\n"
                f"Example: --slurm-rawdata /path/on/hpc/rawdata "
                f"--slurm-derivatives /path/on/hpc/derivatives "
                f"--slurm-apptainer-dir /path/on/hpc/apptainer"
            )


def test_ssh_connection() -> bool:
    """Test SSH connection to HPC."""
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=10", HPC_ADDRESS, "echo", "connected"],
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode == 0 and "connected" in result.stdout:
            logger.info(f"✓ SSH connection to {HPC_ADDRESS} successful")
            return True
        else:
            logger.error(f"SSH connection failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"SSH connection to {HPC_ADDRESS} timed out")
        return False
    except Exception as e:
        logger.error(f"SSH connection error: {e}")
        return False


def generate_slurm_script(
    tool: str,
    participant_label: str,
    dataset: str,
    args: Any,
    hpc_rawdata: str,
    hpc_derivatives: str,
    hpc_apptainer_dir: str
) -> str:
    """Generate SLURM batch script for job submission.
    
    Parameters
    ----------
    tool : str
        Tool name (e.g., 'meld_graph', 'freesurfer', 'fmriprep')
    participant_label : str
        Subject/participant label
    dataset : str
        Dataset name
    args : argparse.Namespace
        Parsed command line arguments
    hpc_rawdata : str
        Path to rawdata on HPC
    hpc_derivatives : str
        Path to derivatives on HPC
    hpc_apptainer_dir : str
        Path to apptainer images on HPC
        
    Returns
    -------
    str
        SLURM batch script content
    """
    job_name = f"{tool}-{dataset}-{participant_label}"
    
    # Build the command to run on HPC
    if tool == "meld_graph":
        # Get the apptainer image path on HPC
        apptainer_img = f"{hpc_apptainer_dir}/meldproject.meld_graph.v2.2.3.sif"
        
        # Build MELD data directory structure on HPC
        meld_data_dir = f"{hpc_derivatives}/meld_graph/{dataset}"
        
        # Determine GPU/CPU settings
        if args.no_gpu:
            gpu_flag = ""
            env_vars = "--env CUDA_VISIBLE_DEVICES=''"
        else:
            gpu_flag = "--nv"
            gpu_mem = getattr(args, 'gpu_memory_limit', 128)
            env_vars = (
                f"--env PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:{gpu_mem},"
                f"garbage_collection_threshold:0.6,expandable_segments:True "
                f"--env CUDA_LAUNCH_BLOCKING=1"
            )
        
        # Build FreeSurfer license path
        fs_license = getattr(args, 'fs_license', '/opt/freesurfer/.license')
        
        # Determine if using precomputed FreeSurfer
        fs_subjects_dir = ""
        if args.use_precomputed_fs:
            fs_derivatives_dir = f"{hpc_derivatives}/fs_outputs/{dataset}"
            fs_subjects_dir = f"-B {fs_derivatives_dir}:/data/output/fs_outputs"
        
        # Build the apptainer command
        cmd = (
            f"apptainer exec {gpu_flag} "
            f"-B {meld_data_dir}:/data "
            f"-B {fs_license}:/license.txt:ro "
            f"--env FS_LICENSE=/license.txt "
            f"{env_vars} "
            f"{fs_subjects_dir} "
            f"{apptainer_img} "
            f"/bin/bash -c 'cd /app && "
            f"python scripts/new_patient_pipeline/new_pt_pipeline.py "
            f"-id sub-{participant_label}"
        )
        
        # Add optional arguments
        if getattr(args, 'harmo_code', None):
            cmd += f" -harmo_code {args.harmo_code}"
        
        if args.skip_segmentation:
            cmd += " --skip_feature_extraction"
        
        cmd += "'"
    
    else:
        raise NotImplementedError(f"SLURM submission for {tool} not yet implemented")
    
    # Generate SLURM script
    script = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --partition={args.slurm_partition}
#SBATCH --time={args.slurm_time}
#SBATCH --mem={args.slurm_mem}
#SBATCH --output={job_name}_%j.out
#SBATCH --error={job_name}_%j.err
"""
    
    # Add GPU request if not using --no-gpu
    if not args.no_gpu:
        script += f"#SBATCH --gres=gpu:{args.slurm_gpus}\n"
    
    script += f"""
# Load required modules (adjust based on HPC configuration)
# module load apptainer  # Uncomment if needed

# Print job information
echo "Job started at: $(date)"
echo "Running on node: $(hostname)"
echo "Job ID: $SLURM_JOB_ID"

# Run the command
{cmd}

# Print completion
echo "Job finished at: $(date)"
"""
    
    return script


def submit_slurm_job(
    tool: str,
    participant_label: str,
    dataset: str,
    args: Any
) -> Optional[str]:
    """Submit job to SLURM HPC cluster.
    
    Parameters
    ----------
    tool : str
        Tool name (e.g., 'meld_graph')
    participant_label : str
        Subject/participant label
    dataset : str
        Dataset name
    args : argparse.Namespace
        Parsed command line arguments
        
    Returns
    -------
    Optional[str]
        Job ID if submission successful, None otherwise
    """
    logger.info(f"Preparing SLURM job for {tool} on {participant_label}...")
    
    # Validate configuration
    validate_slurm_config(args)
    
    # Test SSH connection
    if not test_ssh_connection():
        logger.error("Cannot connect to HPC. Please check SSH configuration.")
        return None
    
    # Generate SLURM script
    script_content = generate_slurm_script(
        tool=tool,
        participant_label=participant_label,
        dataset=dataset,
        args=args,
        hpc_rawdata=args.slurm_rawdata,
        hpc_derivatives=args.slurm_derivatives,
        hpc_apptainer_dir=args.slurm_apptainer_dir
    )
    
    # Create temporary script file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        f.write(script_content)
        local_script = f.name
    
    try:
        # Create remote directory for job scripts
        remote_dir = f"~/ln2t_slurm_jobs/{dataset}"
        subprocess.run(
            ["ssh", HPC_ADDRESS, f"mkdir -p {remote_dir}"],
            check=True,
            capture_output=True
        )
        
        # Copy script to HPC
        remote_script = f"{remote_dir}/{tool}_{participant_label}.sh"
        logger.info(f"Copying job script to {HPC_ADDRESS}:{remote_script}")
        subprocess.run(
            ["scp", local_script, f"{HPC_ADDRESS}:{remote_script}"],
            check=True,
            capture_output=True
        )
        
        # Submit job
        logger.info("Submitting job to SLURM...")
        result = subprocess.run(
            ["ssh", HPC_ADDRESS, f"cd {remote_dir} && sbatch {tool}_{participant_label}.sh"],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse job ID from output (format: "Submitted batch job 12345")
        output = result.stdout.strip()
        if "Submitted batch job" in output:
            job_id = output.split()[-1]
            logger.info(f"✓ Job submitted successfully! Job ID: {job_id}")
            logger.info(f"Monitor with: ssh {HPC_ADDRESS} 'squeue -j {job_id}'")
            logger.info(f"View output: ssh {HPC_ADDRESS} 'cat {remote_dir}/{tool}-{dataset}-{participant_label}_{job_id}.out'")
            return job_id
        else:
            logger.error(f"Unexpected sbatch output: {output}")
            return None
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to submit SLURM job: {e.stderr}")
        return None
    finally:
        # Clean up local temp file
        Path(local_script).unlink(missing_ok=True)


def check_job_status(job_id: str) -> Optional[Dict[str, str]]:
    """Check status of SLURM job.
    
    Parameters
    ----------
    job_id : str
        SLURM job ID
        
    Returns
    -------
    Optional[Dict[str, str]]
        Job status information or None if error
    """
    try:
        result = subprocess.run(
            ["ssh", HPC_ADDRESS, f"squeue -j {job_id} --format='%T|%M|%L'"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # Header + data
                state, time_used, time_left = lines[1].split('|')
                return {
                    'state': state,
                    'time_used': time_used,
                    'time_left': time_left
                }
        return None
    except Exception as e:
        logger.error(f"Error checking job status: {e}")
        return None


def monitor_job(job_id: str, poll_interval: int = 60) -> bool:
    """Monitor SLURM job until completion.
    
    Parameters
    ----------
    job_id : str
        SLURM job ID
    poll_interval : int
        Seconds between status checks (default: 60)
        
    Returns
    -------
    bool
        True if job completed successfully, False otherwise
    """
    logger.info(f"Monitoring job {job_id} (polling every {poll_interval}s)...")
    logger.info("Press Ctrl+C to stop monitoring (job will continue running)")
    
    try:
        while True:
            status = check_job_status(job_id)
            
            if status is None:
                # Job no longer in queue - check if completed
                logger.info(f"Job {job_id} is no longer in queue (completed or failed)")
                return True
            
            logger.info(
                f"Job {job_id}: {status['state']} | "
                f"Running: {status['time_used']} | "
                f"Remaining: {status['time_left']}"
            )
            
            time.sleep(poll_interval)
            
    except KeyboardInterrupt:
        logger.info("\nStopped monitoring. Job continues running on HPC.")
        logger.info(f"Check status with: ssh {HPC_ADDRESS} 'squeue -j {job_id}'")
        return False
