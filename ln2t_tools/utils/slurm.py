"""SLURM HPC cluster job submission utilities."""

import logging
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, Any
import tempfile

logger = logging.getLogger(__name__)

# SSH Configuration
SSH_KEY = "~/.ssh/id_rsa.ceci"
SSH_GATEWAY = "gwceci.ulb.ac.be"  # ProxyJump gateway for CECI clusters


def get_ssh_command(hpc_user: str, hpc_host: str) -> list:
    """Get SSH command with proper key configuration and ProxyJump.
    
    Parameters
    ----------
    hpc_user : str
        Username for HPC cluster
    hpc_host : str
        Hostname for HPC cluster
        
    Returns
    -------
    list
        SSH command with options
    """
    return [
        "ssh",
        "-i", str(Path(SSH_KEY).expanduser()),
        "-J", f"{hpc_user}@{SSH_GATEWAY}",  # ProxyJump through gateway
        "-o", "ConnectTimeout=10",
        f"{hpc_user}@{hpc_host}"
    ]


def get_scp_command(hpc_user: str, hpc_host: str) -> list:
    """Get SCP command with proper key configuration and ProxyJump.
    
    Parameters
    ----------
    hpc_user : str
        Username for HPC cluster
    hpc_host : str
        Hostname for HPC cluster
        
    Returns
    -------
    list
        SCP command with options
    """
    return [
        "scp",
        "-i", str(Path(SSH_KEY).expanduser()),
        "-o", f"ProxyJump={hpc_user}@{SSH_GATEWAY}"  # ProxyJump for SCP
    ]


def validate_slurm_config(args) -> None:
    """Validate SLURM configuration arguments."""
    if args.slurm:
        required_args = {
            '--slurm-user': args.slurm_user,
            '--slurm-apptainer-dir': args.slurm_apptainer_dir,
        }
        
        missing = [arg for arg, value in required_args.items() if not value]
        if missing:
            raise ValueError(
                f"When using --slurm, you must provide: {', '.join(missing)}\n"
                f"Example: --slurm-user arovai "
                f"--slurm-apptainer-dir /path/on/hpc/apptainer\n"
                f"Note: --slurm-rawdata and --slurm-derivatives are optional "
                f"(default: $GLOBALSCRATCH/rawdata and $GLOBALSCRATCH/derivatives on cluster)"
            )


def test_ssh_connection(hpc_user: str, hpc_host: str) -> bool:
    """Test SSH connection to HPC.
    
    Parameters
    ----------
    hpc_user : str
        Username for HPC cluster
    hpc_host : str
        Hostname for HPC cluster
        
    Returns
    -------
    bool
        True if connection successful, False otherwise
    """
    try:
        cmd = get_ssh_command(hpc_user, hpc_host) + ["echo", "connected"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode == 0 and "connected" in result.stdout:
            logger.info(f"✓ SSH connection to {hpc_user}@{hpc_host} successful")
            return True
        else:
            logger.error(f"SSH connection failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"SSH connection to {hpc_user}@{hpc_host} timed out")
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
        Path to rawdata on HPC (can be None to use $GLOBALSCRATCH/rawdata)
    hpc_derivatives : str
        Path to derivatives on HPC (can be None to use $GLOBALSCRATCH/derivatives)
    hpc_apptainer_dir : str
        Path to apptainer images on HPC
        
    Returns
    -------
    str
        SLURM batch script content
    """
    # Use harmo code for job name when harmonizing
    if tool == "meld_graph" and getattr(args, 'harmonize', False):
        job_name = f"meld_harmo-{dataset}-{participant_label}"
    else:
        job_name = f"{tool}-{dataset}-{participant_label}"
    
    # Use $GLOBALSCRATCH if paths not provided (will be evaluated on cluster)
    if not hpc_rawdata:
        hpc_rawdata = "$GLOBALSCRATCH/rawdata"
    if not hpc_derivatives:
        hpc_derivatives = "$GLOBALSCRATCH/derivatives"
    
    # Build the command to run on HPC
    if tool == "meld_graph":
        # Get MELD version
        meld_version = getattr(args, 'version', 'v2.2.3')
        
        # Get the apptainer image path on HPC
        apptainer_img = f"{hpc_apptainer_dir}/meldproject.meld_graph.{meld_version}.sif"
        
        # Determine GPU/CPU settings
        if args.no_gpu:
            gpu_flag = ""
            env_vars = "--env CUDA_VISIBLE_DEVICES=''"
        else:
            gpu_flag = "--nv"
            gpu_mem = getattr(args, 'gpu_memory_limit', 128)
            env_vars = (
                f"--env PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:{gpu_mem} "
                f"--env CUDA_LAUNCH_BLOCKING=1"
            )
        
        # Build FreeSurfer license path (will be evaluated on cluster)
        fs_license_arg = getattr(args, 'slurm_fs_license', None)
        if not fs_license_arg:
            fs_license_arg = "$HOME/licenses/license.txt"
        
        # Determine if using precomputed FreeSurfer
        fs_subjects_dir_bind = ""
        if args.use_precomputed_fs:
            # Match local structure: {dataset}-derivatives/freesurfer_{version}
            fs_version = getattr(args, 'slurm_fs_version', None) or getattr(args, 'fs_version', None) or '7.2.0'
            fs_subjects_dir_bind = f"-B $HPC_DERIVATIVES/$DATASET-derivatives/freesurfer_{fs_version}:/data/output/fs_outputs"
        
        # Build the apptainer command - the whole command will be in the script without quotes
        # so shell variables will be properly expanded
        if getattr(args, 'harmonize', False):
            # Use subjects_list and demographics for harmonization
            harmo_code = getattr(args, 'harmo_code', participant_label)
            python_cmd = (
                f"python scripts/new_patient_pipeline/new_pt_pipeline.py "
                f"-harmo_code {harmo_code} -ids /data/subjects_list.txt "
                f"-demos /data/demographics_{harmo_code}.csv --harmo_only"
            )
        else:
            python_cmd = f"python scripts/new_patient_pipeline/new_pt_pipeline.py -id sub-{participant_label}"
            # Add optional arguments
            if getattr(args, 'harmo_code', None):
                python_cmd += f" -harmo_code {args.harmo_code}"
            if args.skip_segmentation:
                python_cmd += " --skip_feature_extraction"
        
        # Build complete command without quotes around paths so variables expand
        # Note: We don't mount raw data separately - it's symlinked in the MELD input directory
        cmd = (
            f"apptainer exec {gpu_flag} "
            f"-B $HPC_DERIVATIVES/$DATASET-derivatives/meld_graph_$MELD_VERSION/data:/data "
            f"-B {fs_license_arg}:/license.txt:ro "
            f"--env FS_LICENSE=/license.txt "
            f"{env_vars} "
            f"{fs_subjects_dir_bind} "
            f"{apptainer_img} "
            f"/bin/bash -c 'cd /app && {python_cmd}'"
        )
    
    else:
        raise NotImplementedError(f"SLURM submission for {tool} not yet implemented")
    
    # Generate SLURM script
    script = f"""#!/bin/bash
#SBATCH --job-name={job_name}
"""
    
    # Only add partition if specified
    if args.slurm_partition:
        script += f"#SBATCH --partition={args.slurm_partition}\n"
    
    script += f"""#SBATCH --time={args.slurm_time}
#SBATCH --mem={args.slurm_mem}
#SBATCH --output={job_name}_%j.out
#SBATCH --error={job_name}_%j.err
"""
    
    # Add GPU request if not using --no-gpu
    if not args.no_gpu:
        script += f"#SBATCH --gres=gpu:{args.slurm_gpus}\n"
    
    # Add directory setup for MELD Graph
    if tool == "meld_graph":
        meld_version = getattr(args, 'version', 'v2.2.3')
        
        # Define paths as shell variables in the script to be evaluated on cluster
        # Use double $ to escape in Python f-string
        script += f"""
# Define data paths (will be evaluated on cluster)
HPC_RAWDATA="{hpc_rawdata}"
HPC_DERIVATIVES="{hpc_derivatives}"
DATASET="{dataset}"
MELD_VERSION="{meld_version}"

# Setup MELD directory structure on HPC
echo "Creating MELD directory structure..."
MELD_DATA_DIR="$HPC_DERIVATIVES/$DATASET-derivatives/meld_graph_$MELD_VERSION/data"
mkdir -p $MELD_DATA_DIR/input
mkdir -p $MELD_DATA_DIR/output/predictions_reports
mkdir -p $MELD_DATA_DIR/output/fs_outputs
mkdir -p $MELD_DATA_DIR/output/preprocessed_surf_data

# Create MELD configuration files in the input directory
# These must be in input/ where MELD expects them
MELD_CONFIG_FILE="$MELD_DATA_DIR/input/meld_bids_config.json"
if [ ! -f "$MELD_CONFIG_FILE" ]; then
    echo "Creating MELD BIDS config file at $MELD_CONFIG_FILE..."
    cat > "$MELD_CONFIG_FILE" << 'EOF'
{{
  "T1": {{
    "session": null,
    "datatype": "anat",
    "suffix": "T1w"
  }},
  "FLAIR": {{
    "session": null,
    "datatype": "anat",
    "suffix": "FLAIR"
  }}
}}
EOF
fi

DATASET_DESC_FILE="$MELD_DATA_DIR/input/dataset_description.json"
if [ ! -f "$DATASET_DESC_FILE" ]; then
    echo "Creating dataset description file at $DATASET_DESC_FILE..."
    cat > "$DATASET_DESC_FILE" << 'EOF'
{{
  "Name": "{dataset}",
  "BIDSVersion": "1.6.0"
}}
EOF
fi

# Create symlinks from MELD input to raw data
# This way config files stay in place and MELD can access the raw data
echo "Creating symlinks to raw data..."
for subj_dir in $HPC_RAWDATA/$DATASET-rawdata/sub-*; do
    if [ -d "$subj_dir" ]; then
        subj=$(basename $subj_dir)
        if [ ! -e "$MELD_DATA_DIR/input/$subj" ]; then
            ln -s "$subj_dir" "$MELD_DATA_DIR/input/$subj"
            echo "  Linked $subj"
        fi
    fi
done

# Link participants.tsv if present (used to build demographics)
if [ -f "$HPC_RAWDATA/$DATASET-rawdata/participants.tsv" ]; then
    ln -sf "$HPC_RAWDATA/$DATASET-rawdata/participants.tsv" "$MELD_DATA_DIR/input/participants.tsv"
    echo "Linked participants.tsv"
else
    echo "Warning: participants.tsv not found at $HPC_RAWDATA/$DATASET-rawdata/participants.tsv"
fi
"""
        
        # If harmonizing, embed subjects list and generate demographics CSV on-cluster
        if getattr(args, 'harmonize', False):
            # Collect subject labels from either file or inline labels
            subject_labels = []
            try:
                if getattr(args, 'participants_file', None):
                    pf = Path(getattr(args, 'participants_file'))
                    if pf.exists():
                        for line in pf.read_text().splitlines():
                            s = line.strip()
                            if s:
                                subject_labels.append(s)
                    else:
                        logger.warning(f"Participants file not found locally for SLURM embedding: {pf}")
                if not subject_labels and getattr(args, 'participant_label', None):
                    subject_labels = list(getattr(args, 'participant_label'))
            except Exception as e:
                logger.error(f"Error reading participants for SLURM harmonization: {e}")
                subject_labels = []

            # Normalize: ensure 'sub-' prefix when writing
            normalized_lines = []
            for s in subject_labels:
                s = s.strip()
                if not s:
                    continue
                if not s.startswith('sub-'):
                    s = f"sub-{s}"
                normalized_lines.append(s)

            # Write subjects_list.txt via heredoc if we have entries
            if normalized_lines:
                subjects_list_content = "\n".join(normalized_lines) + "\n"
                # Embedded Python snippet to build demographics on-cluster; keep as plain string to avoid f-string brace parsing
                python_snippet = """
import os, sys
import pandas as pd
import pathlib as p

subjects = []
with open("/data/subjects_list.txt") as f:
    for line in f:
        s = line.strip()
        if s:
            if not s.startswith("sub-"):
                s = "sub-" + s
            subjects.append(s)

ptsv = "/data/input/participants.tsv"
if not os.path.exists(ptsv):
    print("participants.tsv not found:", ptsv, file=sys.stderr)
    sys.exit(1)

df = pd.read_csv(ptsv, sep="\t")
df = df[df.get("participant_id", pd.Series(dtype=str)).isin(subjects)].copy()
if df.empty:
    print("No matching participants in participants.tsv", file=sys.stderr)
    sys.exit(1)

demo = pd.DataFrame()
demo["ID"] = df["participant_id"]
demo["Harmo code"] = os.environ.get("HARMOCODE", "H1")

if "group" in df.columns:
    grp = df["group"].astype(str).str.lower()
    demo["Group"] = grp.where(grp.isin(["patient","control"]), "patient")
else:
    demo["Group"] = "patient"

age_col = None
for c in ["age","Age","age_at_preoperative","Age at preoperative"]:
    if c in df.columns:
        age_col = c
        break
if not age_col:
    print("Age column not found in participants.tsv", file=sys.stderr)
    sys.exit(1)
demo["Age at preoperative"] = pd.to_numeric(df[age_col], errors="coerce")
if demo["Age at preoperative"].isna().any():
    print("Missing or invalid age values in participants.tsv for selected subjects", file=sys.stderr)
    sys.exit(1)

sex_col = None
for c in ["sex","Sex","gender","Gender"]:
    if c in df.columns:
        sex_col = c
        break
if not sex_col:
    print("Sex column not found in participants.tsv", file=sys.stderr)
    sys.exit(1)
sex_map = {"M":"male","m":"male","male":"male","Male":"male",
           "F":"female","f":"female","female":"female","Female":"female"}
demo["Sex"] = df[sex_col].map(sex_map)
if demo["Sex"].isna().any():
    print("Invalid sex values for selected subjects", file=sys.stderr)
    sys.exit(1)

out = "/data/demographics_" + os.environ.get("HARMOCODE","H1") + ".csv"
demo.to_csv(out, index=False)
print("Created demographics:", out)
"""
                script += f"""
# Write subjects list for harmonization
SUBJECTS_LIST_FILE="$MELD_DATA_DIR/subjects_list.txt"
cat > "$SUBJECTS_LIST_FILE" << 'EOF'
{subjects_list_content}EOF
echo "Wrote subjects list to $SUBJECTS_LIST_FILE"

# Set harmonization code for demographics
HARMOCODE="{getattr(args, 'harmo_code', participant_label)}"

# Generate demographics CSV inside the container using participants.tsv
apptainer exec {gpu_flag} \
    -B $MELD_DATA_DIR:/data \
    -B {fs_license_arg}:/license.txt:ro \
    --env FS_LICENSE=/license.txt \
    --env HARMOCODE="$HARMOCODE" \
    {apptainer_img} \
    /bin/bash -c 'python - << "PY"
{python_snippet}
PY'
"""
            else:
                logger.warning("No participants provided via --participant-label or --participants-file; harmonization job may fail.")

    script += f"""
# Load required modules (adjust based on HPC configuration)
# module load apptainer  # Uncomment if needed

# Print job information
echo "Job started at: $(date)"
echo "Running on node: $(hostname)"
echo "Job ID: $SLURM_JOB_ID"

# Check if MELD parameters and models are available, download if needed
if [ ! -d "$MELD_DATA_DIR/meld_params/fsaverage_sym" ] || [ ! -d "$MELD_DATA_DIR/models" ]; then
    echo "MELD parameters or models not found, downloading..."
    echo "This is a one-time download and may take several minutes."
    
    # Run prepare_classifier.py to download meld_params and models
    apptainer exec {gpu_flag} \\
        -B $MELD_DATA_DIR:/data \\
        -B {fs_license_arg}:/license.txt:ro \\
        --env FS_LICENSE=/license.txt \\
        {apptainer_img} \\
        /bin/bash -c 'cd /app && python scripts/new_patient_pipeline/prepare_classifier.py --skip-config'
    
    if [ $? -eq 0 ]; then
        echo "✓ Successfully downloaded MELD parameters and models"
    else
        echo "✗ Failed to download MELD parameters and models"
        exit 1
    fi
else
    echo "✓ MELD parameters and models already available"
fi

# Run the main command
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
    
    hpc_user = args.slurm_user
    hpc_host = args.slurm_host
    hpc_address = f"{hpc_user}@{hpc_host}"
    
    # Test SSH connection
    if not test_ssh_connection(hpc_user, hpc_host):
        logger.error("Cannot connect to HPC. Please check SSH configuration.")
        return None
    
    # Note: We don't sync meld_params or models to HPC anymore
    # The SLURM script will automatically download them if needed using prepare_classifier.py
    # This avoids rsync issues and ensures the cluster always has the correct data
    
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
        ssh_cmd = get_ssh_command(hpc_user, hpc_host) + [f"mkdir -p {remote_dir}"]
        subprocess.run(
            ssh_cmd,
            check=True,
            capture_output=True
        )
        
        # Copy script to HPC
        remote_script = f"{remote_dir}/{tool}_{participant_label}.sh"
        logger.info(f"Copying job script to {hpc_address}:{remote_script}")
        scp_cmd = get_scp_command(hpc_user, hpc_host) + [local_script, f"{hpc_address}:{remote_script}"]
        subprocess.run(
            scp_cmd,
            check=True,
            capture_output=True
        )
        
        # Submit job
        logger.info("Submitting job to SLURM...")
        ssh_cmd = get_ssh_command(hpc_user, hpc_host) + [f"cd {remote_dir} && sbatch {tool}_{participant_label}.sh"]
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse job ID from output (format: "Submitted batch job 12345")
        output = result.stdout.strip()
        stderr = result.stderr.strip()
        
        # Log both stdout and stderr for debugging
        logger.info(f"sbatch stdout: '{output}'")
        if stderr:
            logger.info(f"sbatch stderr: '{stderr}'")
        
        if "Submitted batch job" in output:
            # Extract just the job number from the output
            # Format should be: "Submitted batch job 12345"
            parts = output.split()
            if len(parts) >= 4:  # Should have at least "Submitted batch job XXXXX"
                job_id = parts[3]  # Fourth element is the job ID
            else:
                logger.error(f"Unexpected sbatch output format. Parts: {parts}")
                return None
            
            # Validate it's a number
            if not job_id.isdigit():
                logger.error(f"Expected numeric job ID but got: '{job_id}'")
                logger.error(f"Full sbatch output was: '{output}'")
                logger.error(f"Parsed parts: {parts}")
                return None
                
            logger.info(f"✓ Job submitted successfully! Job ID: {job_id}")
            logger.info(f"Monitor with: ssh -i {SSH_KEY} -J {hpc_user}@{SSH_GATEWAY} {hpc_address} 'squeue -j {job_id}'")
            logger.info(f"View output: ssh -i {SSH_KEY} -J {hpc_user}@{SSH_GATEWAY} {hpc_address} 'cat {remote_dir}/{tool}-{dataset}-{participant_label}_{job_id}.out'")
            return job_id
        else:
            logger.error(f"Unexpected sbatch output: '{output}'")
            logger.error(f"Expected format: 'Submitted batch job XXXXX'")
            logger.error(f"Could not parse job ID from sbatch output")
            return None
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to submit SLURM job: {e.stderr}")
        return None
    finally:
        # Clean up local temp file
        Path(local_script).unlink(missing_ok=True)


def check_job_status(job_id: str, hpc_user: str, hpc_host: str) -> Optional[Dict[str, str]]:
    """Check status of SLURM job.
    
    Parameters
    ----------
    job_id : str
        SLURM job ID
    hpc_user : str
        Username for HPC cluster
    hpc_host : str
        Hostname for HPC cluster
        
    Returns
    -------
    Optional[Dict[str, str]]
        Job status information or None if error
    """
    try:
        ssh_cmd = get_ssh_command(hpc_user, hpc_host) + [f"squeue -j {job_id} --format='%T|%M|%L'"]
        result = subprocess.run(
            ssh_cmd,
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


def monitor_job(job_id: str, hpc_user: str, hpc_host: str, poll_interval: int = 60) -> bool:
    """Monitor SLURM job until completion.
    
    Parameters
    ----------
    job_id : str
        SLURM job ID
    hpc_user : str
        Username for HPC cluster
    hpc_host : str
        Hostname for HPC cluster
    poll_interval : int
        Seconds between status checks (default: 60)
        
    Returns
    -------
    bool
        True if job completed successfully, False otherwise
    """
    hpc_address = f"{hpc_user}@{hpc_host}"
    logger.info(f"Monitoring job {job_id} (polling every {poll_interval}s)...")
    logger.info("Press Ctrl+C to stop monitoring (job will continue running)")
    
    try:
        while True:
            status = check_job_status(job_id, hpc_user, hpc_host)
            
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
        logger.info(f"Check status with: ssh -i {SSH_KEY} -J {hpc_user}@{SSH_GATEWAY} {hpc_address} 'squeue -j {job_id}'")
        return False
