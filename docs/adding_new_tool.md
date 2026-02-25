# Adding a New Tool to ln2t_tools

ln2t_tools uses a modular plugin architecture that allows you to add new neuroimaging tools without modifying the core codebase. Each tool is self-contained in its own directory with CLI arguments, validation, and processing logic.

## Quick Start

1. Create a directory: `ln2t_tools/tools/mytool/`
2. Create `__init__.py` and `tool.py`
3. Implement the `BaseTool` interface
4. Add default version to `utils/defaults.py`
5. Register the tool in `utils/utils.py` (image lookup and command builder)
6. Add the tool to the supported tools list in `ln2t_tools.py`
7. Update bash completion (optional but recommended)
8. Your tool is automatically discovered and available!

## Step-by-Step Guide

### 1. Create the Tool Directory

```bash
mkdir -p ln2t_tools/tools/mytool
```

### 2. Create `__init__.py`

```python
# ln2t_tools/tools/mytool/__init__.py
"""My custom neuroimaging tool."""

from .tool import MyTool

# Required: export TOOL_CLASS for auto-discovery
TOOL_CLASS = MyTool

__all__ = ['MyTool', 'TOOL_CLASS']
```

### 3. Create `tool.py` with BaseTool Implementation

```python
# ln2t_tools/tools/mytool/tool.py
"""My custom tool implementation."""

import argparse
import logging
from pathlib import Path
from typing import List, Optional

from bids import BIDSLayout

from ln2t_tools.tools.base import BaseTool
from ln2t_tools.utils.defaults import DEFAULT_MYTOOL_VERSION

logger = logging.getLogger(__name__)


class MyTool(BaseTool):
    """My custom neuroimaging tool.

    Brief description of what the tool does and when to use it.
    """

    # Required class attributes
    name = "mytool"                                    # CLI subcommand name
    help_text = "Brief help shown in ln2t_tools -h"   # Short description
    description = "Detailed tool description"          # Long description
    default_version = DEFAULT_MYTOOL_VERSION           # Default container version
    requires_gpu = False                               # Set True if GPU-accelerated

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add tool-specific CLI arguments.

        Common arguments (--dataset, --participant-label, --version, etc.)
        are added automatically. Only add tool-specific options here.
        """
        parser.add_argument(
            "--my-option",
            default="default_value",
            help="Description of my option (default: default_value)"
        )
        parser.add_argument(
            "--my-flag",
            action="store_true",
            help="Enable special feature"
        )

    @classmethod
    def validate_args(cls, args: argparse.Namespace) -> bool:
        """Validate tool-specific arguments.

        Returns True if arguments are valid, False otherwise.
        Log error messages to explain validation failures.
        """
        # Example: check that required options are set
        if getattr(args, 'my_option', None) == 'invalid':
            logger.error("--my-option cannot be 'invalid'")
            return False
        return True

    @classmethod
    def check_requirements(
        cls,
        layout: BIDSLayout,
        participant_label: str,
        args: argparse.Namespace
    ) -> bool:
        """Check if all requirements are met to process this participant.

        Verify that required input files exist and any prerequisites
        (like FreeSurfer outputs) are available.
        """
        # Example: check for T1w image
        t1w_files = layout.get(
            subject=participant_label,
            suffix='T1w',
            extension=['.nii', '.nii.gz']
        )

        if not t1w_files:
            logger.warning(f"No T1w images found for {participant_label}")
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
        """Get the output directory path for this participant.

        Follow BIDS derivatives naming: {tool}_{version}/sub-{id}/
        """
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

        Returns a list of command components that will be joined
        and executed via Apptainer.
        """
        version = args.version or cls.default_version
        output_dir = cls.get_output_dir(
            dataset_derivatives, participant_label, args
        )

        # Build Apptainer command
        cmd = [
            "apptainer", "run", "--cleanenv",
            # Bind directories
            "-B", f"{dataset_rawdata}:/input:ro",
            "-B", f"{dataset_derivatives}:/output",
            # Container image
            apptainer_img,
            # Tool arguments
            "/input",
            "/output",
            "--participant-label", participant_label,
        ]

        # Add tool-specific options
        if getattr(args, 'my_flag', False):
            cmd.append("--my-flag")

        my_option = getattr(args, 'my_option', 'default_value')
        cmd.extend(["--my-option", my_option])

        return cmd
```

### 4. Add Default Version Constant

Add a default version constant for your tool in `ln2t_tools/utils/defaults.py`. **Important**: Use the exact Docker tag for reproducibility (e.g., `"v1.0.0"` or `"cuda-v2.4.2"`, not just `"1.0.0"`):

```python
# ln2t_tools/utils/defaults.py

# Add with the other default version constants
# Use the EXACT Docker tag for reproducibility
DEFAULT_MYTOOL_VERSION = "v1.0.0"  # Must match Docker Hub tag exactly
```

Then import and use it in your tool:

```python
# ln2t_tools/tools/mytool/tool.py
from ln2t_tools.utils.defaults import DEFAULT_MYTOOL_VERSION

class MyTool(BaseTool):
    default_version = DEFAULT_MYTOOL_VERSION
```

### 5. Register Tool in Utils (Critical Step!)

This step is essential for the tool to work. You must register your tool in two functions in `ln2t_tools/utils/utils.py`:

#### 5.1 Add to `ensure_image_exists()`

This function maps tool names to Docker image owners and handles container building:

```python
# ln2t_tools/utils/utils.py - in ensure_image_exists() function

def ensure_image_exists(tool, version, images_dir, logger):
    """Ensure Apptainer image exists, build from Docker Hub if needed."""

    # ... existing code ...

    # Add your tool to the tool owner mapping
    if tool == "freesurfer":
        tool_owner = "freesurfer"
    elif tool == "fmriprep":
        tool_owner = "nipreps"
    elif tool == "mytool":           # <-- ADD THIS
        tool_owner = "myorg"         # Docker Hub organization/user
    else:
        raise ValueError(f"Unknown tool: {tool}")

    # The version is used directly as the Docker tag
    # Make sure DEFAULT_MYTOOL_VERSION in defaults.py matches the exact Docker tag
```

#### 5.2 Add to `build_apptainer_cmd()`

This function builds the actual Apptainer execution command with all bindings:

```python
# ln2t_tools/utils/utils.py - in build_apptainer_cmd() function

def build_apptainer_cmd(tool, participant_label, args, ...):
    # ... existing code ...

    elif tool == "mytool":
        cmd = [
            "apptainer", "run", "--cleanenv",
            "-B", f"{dataset_rawdata}:/input:ro",
            "-B", f"{dataset_derivatives}:/output",
            apptainer_img,
            "/input", "/output",
            "--participant-label", participant_label,
        ]
        # Add tool-specific options
        if getattr(args, 'my_flag', False):
            cmd.append("--my-flag")
```

**Note**: Without this registration step, running your tool will fail with "Unsupported tool mytool" error!

#### 5.3 Add to Supported Tools List in `ln2t_tools.py`

The main processing loop has a hardcoded list of supported tools. Add your tool to this list:

```python
# ln2t_tools/ln2t_tools.py - in the main processing loop

# Find this line and add your tool:
if tool not in ["freesurfer", "fastsurfer", "fmriprep", "qsiprep", "qsirecon", "meld_graph", "mytool"]:
    logger.warning(f"Unsupported tool {tool} for dataset {dataset}, skipping")
    continue
```

### 6. Update Bash Completion (Optional but Recommended)

Add your tool to `ln2t_tools/completion/ln2t_tools_completion.bash`:

```bash
# Add tool name to the tools list
tools="freesurfer fmriprep qsiprep qsirecon fastsurfer meld_graph mytool"

# Add tool-specific completions
_ln2t_tools_mytool() {
    case "${prev}" in
        --my-option)
            COMPREPLY=( $(compgen -W "value1 value2 value3" -- "${cur}") )
            return 0
            ;;
    esac

    COMPREPLY=( $(compgen -W "--my-option --my-flag --help" -- "${cur}") )
}
```

### 7. Create Apptainer Recipe (Optional)

For tools without pre-built containers, create a recipe in `apptainer_recipes/`:

```bash
# apptainer_recipes/mytool.def
Bootstrap: docker
From: myorg/mytool:1.0.0

%labels
    Author Your Name
    Version 1.0.0
    Description My custom tool container

%post
    # Any additional setup commands
    apt-get update && apt-get install -y curl

%runscript
    exec /opt/mytool/run.sh "$@"
```

#### Recipe Components

**Bootstrap and From**
- **Bootstrap**: Specifies the container system (usually `docker`)
- **From**: The base image from Docker Hub in format `owner/image:tag`

**Labels**
- Metadata about the container (author, version, description)
- Visible when inspecting the built image

**Post Section**
- Shell commands executed during container build
- Install dependencies, download files, configure environment
- Commands run as root

**Runscript Section**
- Entry point executed when the container runs
- Often delegates to the tool's main executable

#### Building the Recipe

`ln2t_tools` automatically builds Apptainer images from recipes stored in `apptainer_recipes/`:

```bash
# ln2t_tools will automatically detect and build your recipe
# Place the recipe as: apptainer_recipes/mytool.def

# Then run your tool normally
ln2t_tools mytool --dataset mydata --participant-label 01
```

The built image will be stored in `/opt/apptainer/` by default.

#### Recipe Best Practices

1. **Use specific versions**: Always pin to exact versions (e.g., `1.0.0` not `latest`)
2. **Minimize layer size**: Combine RUN commands to reduce image size
3. **Clean up**: Remove apt caches and temporary files in %post
4. **Document dependencies**: List external dependencies in comments
5. **Test locally**: Build and test the recipe before committing

#### Example: Complete Recipe

```bash
# apptainer_recipes/mytool.def
Bootstrap: docker
From: ubuntu:22.04

%labels
    Author John Doe
    Version 2.1.0
    Description Advanced neuroimaging tool for brain analysis
    Contact support@example.com

%help
    MyTool - Advanced brain analysis pipeline
    
    Usage:
        apptainer run mytool.sif /input /output --participant-label 001

%environment
    export PATH=$PATH:/opt/mytool/bin
    export TOOL_HOME=/opt/mytool

%post
    apt-get update
    apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        wget \
        ca-certificates
    
    # Install Python dependencies
    pip3 install numpy scipy nibabel
    
    # Download and install tool
    mkdir -p /opt/mytool
    wget -q https://github.com/example/mytool/releases/download/v2.1.0/mytool-2.1.0.tar.gz
    tar -xzf mytool-2.1.0.tar.gz -C /opt/mytool
    rm mytool-2.1.0.tar.gz
    
    # Cleanup
    apt-get clean
    rm -rf /var/lib/apt/lists/*

%runscript
    exec /opt/mytool/bin/mytool "$@"

%test
    /opt/mytool/bin/mytool --version
```

#### Troubleshooting

**Build Fails**
- Check Docker image name and tag exist on Docker Hub
- Verify network connectivity during build
- Check available disk space in `/opt/apptainer/`

**Runtime Errors**
- Add verbose logging to %post to identify build issues
- Test the tool inside container manually with `apptainer shell`
- Check bind mount paths in the tool's `build_command()` method

#### References

- [Apptainer Documentation](https://apptainer.org/docs/)
- [Apptainer Definition Files](https://apptainer.org/docs/user/latest/definition_files/)

### 8. Test Your Tool

```bash
# Verify tool is discovered
ln2t_tools --help
# Should show: mytool - Brief help shown in ln2t_tools -h

# View tool-specific help
ln2t_tools mytool --help

# Run on a participant
ln2t_tools mytool --dataset mydata --participant-label 01 --my-option value
```

## Best Practices

1. **Follow BIDS naming**: Output directories should follow `{tool}_{version}/` pattern
2. **Validate inputs**: Check for required files in `check_requirements()`
3. **Log clearly**: Use `logger.info()` for progress, `logger.warning()` for issues
4. **Handle versions**: Use `args.version or cls.default_version` pattern
5. **Document options**: Provide clear `--help` text for all arguments

## Advanced Features

### Custom Processing Logic

Override `process_subject()` for complex workflows:

```python
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
    """Custom processing with multi-step workflow."""
    # Step 1: Pre-processing
    # Step 2: Main processing
    # Step 3: Post-processing
    return True
```

### HPC Script Generation

Override `generate_hpc_script()` for custom batch scripts:

```python
@classmethod
def generate_hpc_script(
    cls,
    participant_label: str,
    dataset: str,
    args: argparse.Namespace,
    **kwargs
) -> str:
    """Generate custom HPC batch script."""
    return f"""#!/bin/bash
#SBATCH --job-name={cls.name}_{participant_label}
#SBATCH --gpus={1 if cls.requires_gpu else 0}
...
"""
```

## Directory Structure

After adding a tool, your directory structure should look like:

```
ln2t_tools/tools/
├── __init__.py          # Tool registry and discovery
├── base.py              # BaseTool abstract class
├── freesurfer/          # Existing tool
│   ├── __init__.py
│   └── tool.py
├── fmriprep/            # Existing tool
│   ├── __init__.py
│   └── tool.py
└── mytool/              # Your new tool
    ├── __init__.py
    └── tool.py
```
