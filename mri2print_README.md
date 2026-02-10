# mri2print

Convert FreeSurfer brain reconstructions into 3D-printable STL mesh files.

This tool takes the output of FreeSurfer's `recon-all` pipeline and generates high-quality 3D mesh files suitable for 3D printing. It processes both cortical surfaces and subcortical structures, applies smoothing filters, and generates various output combinations.

**Based on:** [Madan (2015) - Creating 3D visualizations of MRI data](https://doi.org/10.12688/f1000research.6838.1)

## Table of Contents

- [Features](#features)
- [Quick Start with Apptainer](#quick-start-with-apptainer)
- [Installation](#installation)
- [Usage](#usage)
- [Parameters and Their Effects](#parameters-and-their-effects)
- [Output Files](#output-files)
- [Input Requirements](#input-requirements)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [License](#license)
- [References](#references)

## Features

- **Complete CLI interface** with help, versioning, and comprehensive options
- **Apptainer/Singularity container** for reproducible execution
- **Verbosity control** - from quiet mode to debug output
- **Logging** - optional file logging for all operations
- **Modular processing** - skip cortex or subcortex as needed
- **Multiple output formats** - full brain, hemispheres, cortex-only, subcortex-only
- **Automatic compression** - gzip output files by default
- **Mesh smoothing** - Taubin smoothing for print-ready surfaces

---

## Quick Start with Apptainer

The easiest way to run mri2print is using the Apptainer (formerly Singularity) container.

### What's Included

The container is self-contained and includes:
- **FreeSurfer 7.4.1** - mri_convert, mri_binarize, mri_pretess, mri_tessellate, mris_convert
- **FSL** - fslmaths
- **pymeshlab** - Mesh processing library
- **meshgeometry** - Surface format conversion

### Prerequisites

You only need:
1. **Apptainer/Singularity** installed on your system
2. **FreeSurfer license file** - Register at [surfer.nmr.mgh.harvard.edu](https://surfer.nmr.mgh.harvard.edu/registration.html) to get a free license

### Building the Container

```bash
# Clone the repository
git clone https://github.com/arovai/mri2print.git
cd mri2print

# Build the Apptainer image (this will download FreeSurfer and FSL)
apptainer build mri2print.sif mri2print.def
```

**Note:** The build process downloads ~10GB of data (FreeSurfer and FSL) and may take 30-60 minutes.

### Running with Apptainer

```bash
apptainer run --cleanenv --containall \
    -B /path/to/freesurfer_license.txt:/opt/freesurfer/license.txt \
    -B /path/to/data:/data \
    mri2print.sif \
    -f /data/freesurfer/sub-01 \
    -o /data/output \
    01
```

**Required bind mounts:**
- `-B /path/to/license.txt:/opt/freesurfer/license.txt` - Your FreeSurfer license file
- `-B /path/to/data:/data` - Your data directories

### Example Commands

```bash
# Show help
apptainer run --cleanenv --containall mri2print.sif --help

# Show version
apptainer run --cleanenv --containall mri2print.sif --version

# Process with verbose output
apptainer run --cleanenv --containall \
    -B ~/freesurfer_license.txt:/opt/freesurfer/license.txt \
    -B $(pwd):/data \
    mri2print.sif \
    -f /data/derivatives/freesurfer/sub-xavier \
    -o /data/output \
    -v \
    xavier
```

---

## Installation

### Option 1: Use Apptainer Container (Recommended)

See [Quick Start with Apptainer](#quick-start-with-apptainer) above.

### Option 2: Native Installation

Install the following dependencies:

| Software | Purpose | Installation |
|----------|---------|--------------|
| **FreeSurfer 6+** | Brain reconstruction tools | [freesurfer.net](https://surfer.nmr.mgh.harvard.edu/) |
| **FSL 5+** | Image manipulation (`fslmaths`) | [fsl.fmrib.ox.ac.uk](https://fsl.fmrib.ox.ac.uk/fsl/) |
| **pymeshlab** | Mesh filtering and smoothing | `pip install pymeshlab` |
| **meshgeometry** | Surface format conversion | [github.com/r03ert0/meshgeometry](https://github.com/r03ert0/meshgeometry) |
| **vcglib** (optional) | Mesh decimation | [github.com/cnr-isti-vclab/vcglib](https://github.com/cnr-isti-vclab/vcglib) |

Then clone and add to PATH:

```bash
git clone https://github.com/arovai/mri2print.git
export PATH="/path/to/mri2print/bin:$PATH"
```

---

## Usage

### Basic Usage

```bash
mri2print <subject_id>

# Or with explicit paths
mri2print -f /path/to/freesurfer/sub-01 -o /path/to/output 01
```

### Command Line Options

```
INPUT/OUTPUT OPTIONS:
  -f, --freesurfer-dir <path>   Path to FreeSurfer subject directory
  -o, --output-dir <path>       Output directory for STL files
  -d, --derivatives <path>      Base derivatives directory (default: ./derivatives)

PROCESSING OPTIONS:
  --decimation <n>              Target face count for mesh decimation
                                (default: 10000000000 - effectively no decimation)
  --skip-cortex                 Skip cortical surface processing
  --skip-subcortex              Skip subcortical structure processing
  --no-compress                 Don't gzip the output STL files

CORTEX SMOOTHING (Taubin filter):
  --cortex-lambda <f>           Lambda parameter (default: 0.6, smoothing strength)
  --cortex-mu <f>               Mu parameter (default: -0.6, inflation factor)
  --cortex-iterations <n>       Number of iterations (default: 70)

SUBCORTEX SMOOTHING (Taubin filter):
  --subcortex-lambda <f>        Lambda parameter (default: 0.6)
  --subcortex-mu <f>            Mu parameter (default: -0.53)
  --subcortex-iterations <n>    Number of iterations (default: 10)

TOOL PATH OPTIONS:
  --meshgeometry <path>         Path to meshgeometry executable
  --tridecimator <path>         Path to tridecimator executable
  --meshlabserver <path>        Path to mesh processing tool

GENERAL OPTIONS:
  -v, --verbose                 Increase verbosity (can stack: -vv, -vvv)
  -q, --quiet                   Suppress all output except errors
  --keep-work                   Keep intermediate working files
  --log-file <path>             Write logs to file
  -h, --help                    Show help message
  --version                     Show version information
```

### Examples

```bash
# Basic processing
mri2print xavier

# Custom input/output directories
mri2print -f /data/freesurfer/sub-001 -o /data/output 001

# Process only cortex (faster)
mri2print --skip-subcortex xavier

# With mesh decimation (reduce polygon count)
mri2print --decimation 100000 xavier

# Verbose output with log file
mri2print -vv --log-file processing.log xavier

# Keep intermediate files for debugging
mri2print --keep-work -vvv xavier

# Custom smoothing: less smoothing for more cortical detail
mri2print --cortex-iterations 30 --cortex-mu -0.55 xavier

# Custom smoothing: more smoothing for smoother print
mri2print --cortex-iterations 100 --subcortex-iterations 20 xavier

# Batch processing
for subj in xavier antonin marie; do
    mri2print -v "$subj"
done
```

---

## Parameters and Their Effects

### Decimation (`--decimation <n>`)

Controls the target face count for mesh simplification.

| Value | Effect | Use Case |
|-------|--------|----------|
| `10000000000` (default) | No decimation | Maximum detail, larger files |
| `500000` | Light decimation | Good detail, smaller files |
| `100000` | Moderate decimation | Balanced detail/size |
| `50000` | Heavy decimation | Fast printing, lower detail |

**Note:** If tridecimator is not available, decimation uses pymeshlab's quadric edge collapse algorithm.

### Smoothing Filters (Taubin)

The tool applies Taubin smoothing to create print-ready surfaces. These parameters can be customized via CLI options (`--cortex-*` and `--subcortex-*`).

**Cortex defaults:**
| Parameter | Default | CLI Option | Effect |
|-----------|---------|------------|--------|
| Lambda | 0.6 | `--cortex-lambda` | Smoothing strength (positive = shrink) |
| Mu | -0.6 | `--cortex-mu` | Inflation factor (negative = expand) |
| Iterations | 70 | `--cortex-iterations` | Number of smoothing passes |

**Subcortex defaults:**
| Parameter | Default | CLI Option | Effect |
|-----------|---------|------------|--------|
| Lambda | 0.6 | `--subcortex-lambda` | Smoothing strength |
| Mu | -0.53 | `--subcortex-mu` | Inflation factor |
| Iterations | 10 | `--subcortex-iterations` | Number of smoothing passes |

**Effect of parameters:**
- **Iterations**: Higher = smoother but may lose fine details. Try 30-50 for more cortical detail, 100+ for very smooth prints.
- **Lambda**: Controls shrinkage per iteration. Higher values = more aggressive smoothing.
- **Mu**: Compensates for shrinkage. Should be negative and close to -lambda to preserve volume.

**Tips:**
- For preserving sulci/gyri detail: reduce iterations (e.g., `--cortex-iterations 30`)
- For smoother prints: increase iterations (e.g., `--cortex-iterations 100`)
- Subcortical structures need less smoothing to preserve their distinct shapes

### Verbosity Levels (`-v`)

| Level | Flag | Output |
|-------|------|--------|
| 0 | `-q` | Errors only |
| 1 | (default) | Info messages |
| 2 | `-v` | Debug messages |
| 3 | `-vv` or `-vvv` | Full command output |

---

## Output Files

The script generates the following STL files:

| File | Description |
|------|-------------|
| `sub-<id>_desc-full.stl.gz` | Complete brain (cortex + subcortical) |
| `sub-<id>_desc-cortex.stl.gz` | Cortical surface (both hemispheres) |
| `sub-<id>_desc-cortex_lh.stl.gz` | Left hemisphere cortex |
| `sub-<id>_desc-cortex_rh.stl.gz` | Right hemisphere cortex |
| `sub-<id>_desc-full_lh.stl.gz` | Left hemisphere + subcortical |
| `sub-<id>_desc-full_rh.stl.gz` | Right hemisphere + subcortical |
| `sub-<id>_desc-subcortical.stl.gz` | Subcortical structures |
| `sub-<id>_desc-subcortical_lh.stl.gz` | Left subcortical |
| `sub-<id>_desc-subcortical_rh.stl.gz` | Right subcortical |
| `sub-<id>_provenance.log` | Processing provenance log |

**Note:** Files are gzipped by default. Use `--no-compress` to keep uncompressed.

### Provenance Log

Each run generates a provenance log file (`sub-<id>_provenance.log`) containing:
- The exact command line used
- Timestamp and version information
- All processing parameters (smoothing settings, decimation target, etc.)

This file is useful for reproducibility and documenting how each brain model was generated.

### Using the Output

1. **Decompress:** `gunzip sub-xavier_desc-full.stl.gz`
2. **Open in slicer software:** Cura, PrusaSlicer, Simplify3D
3. **Scale:** Models are in millimeters at native MRI resolution

---

## Input Requirements

The script requires FreeSurfer `recon-all` output:

```
<freesurfer_subject_dir>/
├── mri/
│   ├── aseg.mgz          # Subcortical segmentation (required)
│   └── norm.mgz          # Normalized T1 (required for subcortex)
└── surf/
    ├── lh.pial           # Left hemisphere pial surface
    └── rh.pial           # Right hemisphere pial surface
```

### Running FreeSurfer recon-all

```bash
# Basic processing
recon-all -s sub-xavier -i /path/to/T1.nii.gz -all

# For 3T scanner data
recon-all -s sub-xavier -i /path/to/T1.nii.gz -all -3T
```

**Note:** `recon-all` takes 6-24 hours depending on hardware.

---

## Project Structure

```
mri2print/
├── bin/
│   ├── mri2print              # Main CLI script
│   ├── version-bump           # Version management script
│   └── filters/
│       ├── decimate.mlx           # Decimation filter
│       ├── taubin.cortex.mlx      # Cortex smoothing filter
│       └── taubin.subcortex.mlx   # Subcortex smoothing filter
├── lib/
│   └── utils.sh               # Shared utility functions
├── VERSION                    # Version number (single source of truth)
├── CHANGELOG.md               # Release history
├── mri2print.def              # Apptainer container definition
├── README.md
└── LICENSE

Output directory structure:
output/
├── sub-<id>_desc-*.stl.gz     # 3D mesh files (various combinations)
└── sub-<id>_provenance.log    # Processing log with command line and parameters
```

---

## Troubleshooting

### Common Issues

**"FreeSurfer home not found"**
```bash
export FREESURFER_HOME=/path/to/freesurfer
# Or use: mri2print --freesurfer-home /path/to/freesurfer xavier
```

**"fslmaths: command not found"**
```bash
source $FSLDIR/etc/fslconf/fsl.sh
export PATH=$FSLDIR/bin:$PATH
```

**"meshgeometry not found"**
```bash
mri2print --meshgeometry /path/to/meshgeometry_linux xavier
```

**Container: FreeSurfer license error**
```bash
# Ensure your license file is bind-mounted correctly
apptainer run --cleanenv --containall \
    -B /path/to/your/license.txt:/opt/freesurfer/license.txt \
    mri2print.sif ...
```

### Debug Mode

```bash
mri2print -vvv --keep-work --log-file debug.log xavier
```

This will:
- Show all command executions
- Keep intermediate files in `work/` directory
- Write complete logs to `debug.log`

---

## Versioning

This project uses [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes or major rewrites
- **MINOR**: New features, backwards compatible
- **PATCH**: Bug fixes, backwards compatible

### Version Management

```bash
# Show current version
./bin/version-bump --show

# Bump patch version (2.0.0 -> 2.0.1)
./bin/version-bump patch

# Bump minor version (2.0.0 -> 2.1.0)
./bin/version-bump minor

# Bump major version and create git tag
./bin/version-bump major --tag
```

The version is defined in `VERSION` file and automatically synced to `mri2print.def`.

See [CHANGELOG.md](CHANGELOG.md) for release history.

---

## License

This project is provided as-is for research and personal use.

---

## References

- Madan, C.R. (2015). Creating 3D visualizations of MRI data: A brief guide. F1000Research, 4:466. [DOI](https://doi.org/10.12688/f1000research.6838.1)
- FreeSurfer: https://surfer.nmr.mgh.harvard.edu/
- FSL: https://fsl.fmrib.ox.ac.uk/
- pymeshlab: https://pymeshlab.readthedocs.io/
- meshgeometry: https://github.com/r03ert0/meshgeometry
- vcglib: https://github.com/cnr-isti-vclab/vcglib
- Apptainer: https://apptainer.org/
