"""HPC cluster job status tracking and monitoring.

Provides utilities to query SLURM job status, parse job states, and track
job history across multiple sessions.
"""

import json
import logging
import re
import subprocess
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)


class JobState(Enum):
    """SLURM job states."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    OUT_OF_MEMORY = "OUT_OF_MEMORY"
    NODE_FAIL = "NODE_FAIL"
    UNKNOWN = "UNKNOWN"


class JobStatus(Enum):
    """Human-readable job status categories."""
    PENDING = "Pending"
    RUNNING = "Running"
    COMPLETED = "Completed successfully"
    FAILED = "Failed"
    TIMEOUT = "Timed out"
    CANCELLED = "Cancelled"
    ERROR = "Error"


@dataclass
class JobInfo:
    """Information about a submitted HPC job."""
    job_id: str
    tool: str
    dataset: str
    participant: str
    submit_time: str  # ISO format timestamp
    state: str = "UNKNOWN"
    exit_code: Optional[int] = None
    reason: Optional[str] = None  # Why job ended (e.g., "TIME_LIMIT_EXCEEDED")
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    elapsed_time: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobInfo':
        """Create from dictionary."""
        return cls(**data)
    
    @property
    def status_category(self) -> JobStatus:
        """Get human-readable status category."""
        state = self.state.upper()
        
        if state in ["PENDING", "CONFIGURING"]:
            return JobStatus.PENDING
        elif state in ["RUNNING", "STAGE_OUT"]:
            return JobStatus.RUNNING
        elif state == "COMPLETED":
            if self.exit_code == 0:
                return JobStatus.COMPLETED
            else:
                # Failed with non-zero exit code
                if self.reason and "TIME_LIMIT" in self.reason:
                    return JobStatus.TIMEOUT
                elif self.reason and "OUT_OF_MEMORY" in self.reason:
                    return JobStatus.ERROR
                else:
                    return JobStatus.FAILED
        elif state in ["CANCELLED", "CANCELLED+"]:
            if self.reason and "TIME_LIMIT" in self.reason:
                return JobStatus.TIMEOUT
            else:
                return JobStatus.CANCELLED
        elif state in ["FAILED", "NODE_FAIL"]:
            return JobStatus.FAILED
        else:
            return JobStatus.ERROR


def get_job_storage_dir() -> Path:
    """Get directory for storing job metadata.
    
    Returns
    -------
    Path
        Directory path for job tracking files
    """
    job_dir = Path.home() / ".ln2t_tools"
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


def save_job_info(job_info: JobInfo) -> None:
    """Save job information to local storage.
    
    Parameters
    ----------
    job_info : JobInfo
        Job information to save
    """
    job_dir = get_job_storage_dir()
    jobs_file = job_dir / "hpc_jobs.json"
    
    # Load existing jobs
    jobs = {}
    if jobs_file.exists():
        try:
            with open(jobs_file, 'r') as f:
                jobs = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not read job storage file: {e}")
            jobs = {}
    
    # Update or add job
    jobs[job_info.job_id] = job_info.to_dict()
    
    # Save back
    try:
        with open(jobs_file, 'w') as f:
            json.dump(jobs, f, indent=2)
    except IOError as e:
        logger.warning(f"Could not save job information: {e}")


def load_all_jobs() -> Dict[str, JobInfo]:
    """Load all saved job information.
    
    Returns
    -------
    Dict[str, JobInfo]
        Dictionary mapping job IDs to JobInfo objects
    """
    job_dir = get_job_storage_dir()
    jobs_file = job_dir / "hpc_jobs.json"
    
    if not jobs_file.exists():
        return {}
    
    try:
        with open(jobs_file, 'r') as f:
            jobs_data = json.load(f)
        
        jobs = {}
        for job_id, job_dict in jobs_data.items():
            try:
                jobs[job_id] = JobInfo.from_dict(job_dict)
            except (TypeError, ValueError) as e:
                logger.warning(f"Could not load job {job_id}: {e}")
        
        return jobs
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Could not load job storage: {e}")
        return {}


def get_job_by_id(job_id: str) -> Optional[JobInfo]:
    """Get job information by job ID.
    
    Parameters
    ----------
    job_id : str
        Job ID to look up
        
    Returns
    -------
    Optional[JobInfo]
        Job information if found
    """
    jobs = load_all_jobs()
    return jobs.get(job_id)


def get_jobs_for_dataset(dataset: str) -> List[JobInfo]:
    """Get all jobs for a specific dataset.
    
    Parameters
    ----------
    dataset : str
        Dataset name
        
    Returns
    -------
    List[JobInfo]
        List of jobs for dataset
    """
    jobs = load_all_jobs()
    return [job for job in jobs.values() if job.dataset == dataset]


def get_jobs_for_tool(tool: str) -> List[JobInfo]:
    """Get all jobs for a specific tool.
    
    Parameters
    ----------
    tool : str
        Tool name
        
    Returns
    -------
    List[JobInfo]
        List of jobs for tool
    """
    jobs = load_all_jobs()
    return [job for job in jobs.values() if job.tool == tool]


def query_squeue_status(
    job_id: str,
    username: str,
    hostname: str,
    keyfile: str,
    gateway: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Query squeue for running job status.
    
    Parameters
    ----------
    job_id : str
        SLURM job ID
    username : str
        HPC username
    hostname : str
        HPC hostname
    keyfile : str
        SSH key path
    gateway : Optional[str]
        ProxyJump gateway
        
    Returns
    -------
    Optional[Dict[str, Any]]
        Job status dict or None if not found
    """
    from .hpc import get_ssh_command
    
    try:
        # Query running jobs with squeue
        cmd = get_ssh_command(username, hostname, keyfile, gateway) + [
            f"squeue -j {job_id} --format='%i:%T:%S:%e' --noheader"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            return None  # Job not found in queue
        
        output = result.stdout.strip()
        if not output:
            return None
        
        # Parse squeue output: job_id:state:start_time:end_time
        parts = output.split(':')
        if len(parts) >= 2:
            return {
                'job_id': parts[0],
                'state': parts[1],
                'start_time': parts[2] if len(parts) > 2 else None,
                'end_time': parts[3] if len(parts) > 3 else None,
            }
        
        return None
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout querying squeue for job {job_id}")
        return None
    except Exception as e:
        logger.debug(f"Error querying squeue: {e}")
        return None


def query_sacct_status(
    job_id: str,
    username: str,
    hostname: str,
    keyfile: str,
    gateway: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Query sacct for completed job status.
    
    Parameters
    ----------
    job_id : str
        SLURM job ID
    username : str
        HPC username
    hostname : str
        HPC hostname
    keyfile : str
        SSH key path
    gateway : Optional[str]
        ProxyJump gateway
        
    Returns
    -------
    Optional[Dict[str, Any]]
        Job status dict or None if not found
    """
    from .hpc import get_ssh_command
    
    try:
        # Query job accounting with sacct
        # Format: jobid:state:exitcode:reason:start:end:elapsed
        cmd = get_ssh_command(username, hostname, keyfile, gateway) + [
            f"sacct -j {job_id} --format='JobID,State,ExitCode,Reason,Start,End,Elapsed' "
            f"--parsable2 --noheader"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            logger.debug(f"sacct query failed for job {job_id}: {result.stderr}")
            return None
        
        output = result.stdout.strip()
        if not output:
            return None
        
        # Parse sacct output (first line is the job, subsequent lines are steps)
        lines = output.split('\n')
        if not lines:
            return None
        
        # Parse first line (main job)
        parts = lines[0].split('|')
        if len(parts) >= 5:
            exit_code = parts[2] if parts[2] else None
            # Extract numeric exit code (format can be "0:0" or "0")
            if exit_code:
                exit_code = int(exit_code.split(':')[0])
            
            return {
                'job_id': parts[0],
                'state': parts[1],
                'exit_code': exit_code,
                'reason': parts[3] if parts[3] else None,
                'start_time': parts[4] if len(parts) > 4 else None,
                'end_time': parts[5] if len(parts) > 5 else None,
                'elapsed_time': parts[6] if len(parts) > 6 else None,
            }
        
        return None
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout querying sacct for job {job_id}")
        return None
    except Exception as e:
        logger.debug(f"Error querying sacct: {e}")
        return None


def check_job_status(
    job_id: str,
    username: str,
    hostname: str,
    keyfile: str,
    gateway: Optional[str] = None
) -> Tuple[JobStatus, Dict[str, Any]]:
    """Check status of a job on HPC cluster.
    
    Queries both squeue (running jobs) and sacct (historical jobs).
    
    Parameters
    ----------
    job_id : str
        SLURM job ID
    username : str
        HPC username
    hostname : str
        HPC hostname
    keyfile : str
        SSH key path
    gateway : Optional[str]
        ProxyJump gateway
        
    Returns
    -------
    Tuple[JobStatus, Dict[str, Any]]
        Status category and detailed status info
    """
    # First try squeue (running jobs)
    status_info = query_squeue_status(job_id, username, hostname, keyfile, gateway)
    
    if status_info:
        state = status_info.get('state', 'UNKNOWN').upper()
        return _state_to_status(state, None), status_info
    
    # If not in squeue, try sacct (finished jobs)
    status_info = query_sacct_status(job_id, username, hostname, keyfile, gateway)
    
    if status_info:
        state = status_info.get('state', 'UNKNOWN').upper()
        exit_code = status_info.get('exit_code')
        reason = status_info.get('reason')
        return _state_to_status(state, reason), status_info
    
    # Job not found
    return JobStatus.ERROR, {'state': 'NOT_FOUND'}


def _state_to_status(state: str, reason: Optional[str]) -> JobStatus:
    """Convert SLURM state to status category.
    
    Parameters
    ----------
    state : str
        SLURM job state
    reason : Optional[str]
        Reason for job ending
        
    Returns
    -------
    JobStatus
        Status category
    """
    state = state.upper()
    
    if state in ["PENDING", "CONFIGURING"]:
        return JobStatus.PENDING
    elif state in ["RUNNING", "STAGE_OUT"]:
        return JobStatus.RUNNING
    elif state == "COMPLETED":
        return JobStatus.COMPLETED
    elif state in ["CANCELLED", "CANCELLED+"]:
        if reason and "TIME_LIMIT" in reason:
            return JobStatus.TIMEOUT
        else:
            return JobStatus.CANCELLED
    elif state == "FAILED" or state == "NODE_FAIL":
        if reason and "TIME_LIMIT" in reason:
            return JobStatus.TIMEOUT
        else:
            return JobStatus.FAILED
    else:
        return JobStatus.ERROR


def format_job_status_report(job_info: JobInfo, status: JobStatus, details: Dict[str, Any]) -> str:
    """Format job status as a human-readable report.
    
    Parameters
    ----------
    job_info : JobInfo
        Job information
    status : JobStatus
        Status category
    details : Dict[str, Any]
        Detailed status information
        
    Returns
    -------
    str
        Formatted report
    """
    status_emoji = {
        JobStatus.PENDING: "⏳",
        JobStatus.RUNNING: "▶️",
        JobStatus.COMPLETED: "✅",
        JobStatus.FAILED: "❌",
        JobStatus.TIMEOUT: "⏱️",
        JobStatus.CANCELLED: "⛔",
        JobStatus.ERROR: "⚠️",
    }
    
    emoji = status_emoji.get(status, "❓")
    
    report = f"{emoji} Job {job_info.job_id} - {status.value}\n"
    report += f"  Tool: {job_info.tool}\n"
    report += f"  Dataset: {job_info.dataset}\n"
    report += f"  Participant: {job_info.participant}\n"
    report += f"  Submitted: {job_info.submit_time}\n"
    
    if details.get('state'):
        report += f"  State: {details['state']}\n"
    
    if details.get('start_time'):
        report += f"  Started: {details['start_time']}\n"
    
    if details.get('end_time'):
        report += f"  Ended: {details['end_time']}\n"
    
    if details.get('elapsed_time'):
        report += f"  Duration: {details['elapsed_time']}\n"
    
    if details.get('exit_code') is not None:
        report += f"  Exit Code: {details['exit_code']}\n"
    
    if details.get('reason'):
        report += f"  Reason: {details['reason']}\n"
    
    return report
