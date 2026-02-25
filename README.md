<div align="center">

# ln2t_tools

**Neuroimaging pipeline manager for the [LN2T](https://ln2t.ulb.be/)**

[How it works](#how-it-works) | [Installation](#intallation) | [How to use it](#how-to-use-it) | [Supported tools](#supported-tools) | [Using HPC](#using-hpc) | [Data organization](#data-organization) | [Bonuses](#bonuses)

</div>

## How it works

`ln2t_tools` is a Command Line Interface software that facilitates execution of standard neuroimaging pipelines. The core principles are:
- Data are supposed to be organized following the [data organization](#data-organization) of the lab, which itself greatly relies on the [Brain Imaging Data Structure (BIDS)](#https://bids-specification.readthedocs.io/en/stable/).
- A [selection of standard pipelines](#supported-tools) have been incorporated in `ln2t_tools` in the form of apptainer images. The installation of the software, for any valid version, is fully automated.
- Outputs are tagged with pipeline name and version number.
- The syntax of `ln2t_tools` is as follows:
  ```bash
  ln2t_tools <pipeline_name> --dataset <dataset_name> [options]
  ```
  There are two classes of options: those belonging to `ln2t_tools` and those that are directly passed to the pipeline; see below for more details and examples.
- By default, the processing is done on the local machine, but `ln2t_tools` can be used to send the work to High-Performance Computing (HPC) Clusters such as [CECI](#https://www.ceci-hpc.be/); more info in the [corresponding section](#using-hpc).
- More pipelines can be added easily thanks to the modular architecture of `ln2t_tools`, but this is not meant to be done by the standard end-user.

If you are interested in using this tool in your lab, make sure to read this documentation in full, in particular the sections describing the [data organization](#data-organization).

## Installation

If you are working on a computer of the lab, the software is already installed and you can skip this section.

To install `ln2t_tools`, we strongly recommend you use a python virtual environment:
```bash
git clone git@github.com:ln2t/ln2t_tools.git
cd ln2t_tools
python -m venv venv
source venv/bin/activate
pip install -U pip
pip install -U .
```

After installation, you can enable bash completion tools using
```bash
echo "source ~/.local/share/bash-completion/completions/ln2t_tools" >> ~/.bashrc
```
and then source `~/.bashrc`. More details in the [How it works](#how-it-works) section.

`ln2t_tools` assumes a standardized folder structure to access raw data and to save outputs; see the [corresponding section](#data-organization) for more details.

Moreover, ln2t_tools uses [Apptainer](https://apptainer.org/) containers to run neuroimaging pipelines. This ensures reproducibility and eliminates dependency conflicts.

**Installation**:
- Apptainer must be installed system-wide
- Container images are stored in `/opt/apptainer` by default

**Permissions**:
The `/opt/apptainer` directory requires write access for pulling and caching container images:
```bash
# Create directory with proper permissions (requires sudo)
sudo mkdir -p /opt/apptainer
sudo chown -R $USER:$USER /opt/apptainer
sudo chmod -R 755 /opt/apptainer
```

Alternatively, you can use a custom directory:
```bash
ln2t_tools freesurfer --dataset mydataset --apptainer-dir /path/to/custom/dir
```

Finally, several pipelines requires a valid license file (free academic license available at [FreeSurfer Registration](https://surfer.nmr.mgh.harvard.edu/registration.html)).

**Default License Location**:
```bash
~/licenses/license.txt
```

To use a custom license location:
```bash
ln2t_tools freesurfer --dataset mydataset --fs-license /path/to/license.txt
```

## How to use it

Open a terminal, start typing `ln2t_tools` and try the auto-completion mechanism using the `<TAB>` key: it will show you the available tools and guide you to complete the command (including dataset name discovery!).

For instance, typing
```bash
ln2t_tools <TAB>  # show you the available tools
```
will show you the [supported tools](#supported-tools), e.g. `freesurfer` or `fmriprep`. Once the pipeline is completed, you can just continue using `<TAB>` to see what must be provided:
```bash
ln2t_tools freesurfer <TAB>  # auto-complete the next argument, in this case '--dataset'
```
This will auto-complete the mandatory argument `--dataset`. Further `<TAB>` presses will show you the datasets you have access to:
```bash
ln2t_tools freesurfer --dataset <TAB>  # show you the available datasets
```
Dataset names in the lab have the structure
```bash
YYYY-Custom_Name-abc123
```
The `YYYY` corresponds to the year of dataset creation; `Custom_Name` is an easy to remember, human-readable name (typically an adjective and an animal) and the end of the name, `abc123`, is a randomly generated sequence of characters. Againg, start typing then use `<TAB>` to auto-complete.

**Example: `FreeSurfer`**

To run `FreeSurfer` on the dataset `2025-Charming_Nightingale-9f9014dbdfae`, you can use
```bash
ln2t_tools freesurfer --dataset 2025-Charming_Nightingale-9f9014dbdfae
```
Pressing enter will:
- select the default version for `FreeSurfer`
- check that it is installed - if not, download and install it
- check that the dataset exists and discover the available subjects
- for each subject, check if `FreeSurfer` has already been run
- launch sequentially the remaining subjects
To understand where to find the outputs, make sure to read to [Data organisation](#data-organization) section.

**Important Notice:**

We **do not** recommend that you launch a tool on a whole dataset at once. Start first on a few subjects - for this, you can use the `ln2t_tools` option `--participant-label`:
```bash
ln2t_tools freesurfer --dataset 2025-Charming_Nightingale-9f9014dbdfae \
            --participant-label 001 042
```
If the processing is successful and corresponds to your needs, then you may consider launching a full dataset run by omitting the `--participant-label` option.

## Supported tools

Here is the list of currently supported tools available to the lab members - for each tool, we show also the typesetting to use when using `ln2t_tools`:

- **FreeSurfer** - `freesurfer`: Cortical reconstruction and surface-based analysis ([official docs](https://surfer.nmr.mgh.harvard.edu/))
- **fMRIPrep** - `fmriprep`: Functional MRI preprocessing ([official docs](https://fmriprep.org/))
- **QSIPrep** - `qsiprep`: Diffusion MRI preprocessing ([official docs](https://qsiprep.readthedocs.io/))
- **QSIRecon** - `qsirecon`: Diffusion MRI reconstruction ([official docs](https://qsiprep.readthedocs.io/))
- **MELD Graph** - `meld_graph`: Lesion detection ([official docs](https://meld-graph.readthedocs.io/))

Note that there is another tool, `ln2t_tools import`, designed to deal with the BIDS-ification of source data. This tool is for administrators only (if you try it it will fail).

## Using HPC

The main neuroimaging tools in `ln2t_tools` like `FreeSurfer`, `fMRIPrep`, `QSIPrep` and `QSIRecon` can be submitted to HPC clusters using SLURM (Simple Linux Utility for Resource Management) using `--hpc`. A typical command look like
```bash
ln2t_tools <pipeline> --dataset <dataset> --hpc --hpc-host <host> --hpc-user <user> --hpc-time 10:00:00
```
`ln2t_tools` will then search for pre-installed SSH keys to interact with the cluster. Data, apptainer images and code will by default be assumed to be located on `$GLOBALSCRATCH`, which is typically an environment variable defined on the cluster. Logs of `ln2t_tools` are in your cluster home folder.

## Data organization

`ln2t_tools` essentially follows the [BIDS (Brain Imaging Data Structure) specification](https://bids-specification.readthedocs.io/) for organizing neuroimaging data, and what follow is essential for the tool to work:

- **Raw data**: `~/rawdata/{dataset}-rawdata` | This is where your original data are stored. You should have read-only permissions for safety.
- **Derivatives**: `~/derivatives/{dataset}-derivatives` | This is where `ln2t_tools` will write (and in some cases, read) outputs of the selected pipeline. For instance, for `FreeSurfer` version `7.2.0`, you will find the results in `~/derivatives/{dataset}-derivatives/freesurfer_7.2.0/sub-*`.
- **Code**: `~/code/{dataset}-code` | The golden spot to put your custom code and configurations. We recommend that you keep there a `README.md` file with copies of the command lines you use - this can be very useful to keep track of your work or to re-run analyzes. Moreover, this folder is made available to the tools that require a configuration file (such a `qsirecon`).

A part from that, there is also a similar structure for the source data (data as exported from the scanner or any other recording device), but these are not generally made available to the users - all you need should be in the raw data.

### Directory Structure

All datasets are organized under your home directory:

```
~/
├── sourcedata/
│   └── {dataset}-sourcedata/
│       ├── dicom/                          # DICOM files from scanner
│       ├── physio/                         # Physiological recordings (GE scanner)
│       ├── mrs/                            # Magnetic Resonance Spectroscopy data
│       ├── meg/                            # MEG data from Neuromag/Elekta/MEGIN
│       │   ├── meg_XXXX/                   # MEG subject folders (4-digit ID)
│       │   │   └── YYMMDD/                 # Session date folders
│       │   │       └── *.fif               # MEG FIF files
│       │   └── ...
│       └── configs/                        # Configuration files
│           ├── dcm2bids.json              # DICOM to BIDS conversion config
│           ├── spec2bids.json             # MRS to BIDS conversion config
│           ├── physio.json                # Physiological data processing config
│           └── meg2bids.json              # MEG to BIDS conversion config
│
├── rawdata/
│   └── {dataset}-rawdata/                  # BIDS-formatted data
│       ├── dataset_description.json
│       ├── participants.tsv
│       ├── sub-{id}/
│       │   ├── anat/
│       │   │   ├── sub-{id}_T1w.nii.gz
│       │   │   ├── sub-{id}_T2w.nii.gz
│       │   │   └── sub-{id}_FLAIR.nii.gz
│       │   ├── func/
│       │   │   ├── sub-{id}_task-{name}_bold.nii.gz
│       │   │   └── sub-{id}_task-{name}_bold.json
│       │   ├── dwi/
│       │   │   ├── sub-{id}_dwi.nii.gz
│       │   │   ├── sub-{id}_dwi.bval
│       │   │   └── sub-{id}_dwi.bvec
│       │   ├── mrs/
│       │   │   ├── sub-{id}_svs.nii.gz
│       │   │   └── sub-{id}_svs.json
│       │   ├── meg/
│       │   │   ├── sub-{id}_task-{name}_meg.fif
│       │   │   ├── sub-{id}_task-{name}_meg.json
│       │   │   ├── sub-{id}_task-{name}_channels.tsv
│       │   │   ├── sub-{id}_acq-crosstalk_meg.fif
│       │   │   └── sub-{id}_acq-calibration_meg.dat
│       │   └── func/ (physiological recordings)
│       │       ├── sub-{id}_task-{name}_recording-cardiac_physio.tsv.gz
│       │       ├── sub-{id}_task-{name}_recording-cardiac_physio.json
│       │       ├── sub-{id}_task-{name}_recording-respiratory_physio.tsv.gz
│       │       └── sub-{id}_task-{name}_recording-respiratory_physio.json
│
├── derivatives/
│   └── {dataset}-derivatives/
│       ├── freesurfer_{version}/          # FreeSurfer outputs
│       ├── fmriprep_{version}/            # fMRIPrep outputs
│       ├── qsiprep_{version}/             # QSIPrep outputs
│       ├── qsirecon_{version}/            # QSIRecon outputs
│       ├── maxfilter_{version}/           # MaxFilter MEG derivatives
│       └── meld_graph_{version}/          # MELD Graph outputs
│
└── code/
    └── {dataset}-code/
        └── meld_graph_{version}/
            └── config/                     # MELD configuration files
                ├── meld_bids_config.json
                └── dataset_description.json
```

## Bonuses

### Tool-Specific Arguments with --tool-args

`ln2t_tools` uses a pass-through argument pattern for tool-specific options. This allows the tools to be updated independently of `ln2t_tools`, and gives you access to the full range of options each tool supports.

Core arguments (dataset, participant, version, HPC options) are handled by `ln2t_tools`. Tool-specific arguments are passed verbatim to the container using `--tool-args`:

```bash
ln2t_tools <tool> --dataset mydataset --participant-label 01 --tool-args "<tool-specific-arguments>"
```
For instance, here what you shoud do to use `qsiprep` with the (mandatory) argument `--output-resolution`:
```bash
ln2t_tools qsiprep --dataset mydataset --participant-label 01 \
    --tool-args "--output-resolution 1.5"
```

### Finding Missing Participants

The `--list-missing` flag helps identify which participants in your dataset still need processing for a specific tool. This is useful when:
- Resuming incomplete pipelines after errors
- Managing large cohorts with multiple tools
- Generating copy-paste commands to process missing participants

---

### MELD Graph

MELD Graph performs automated FCD (Focal Cortical Dysplasia) lesion detection using FreeSurfer surfaces and deep learning.

#### Default Values
- **Version**: `v2.2.3`
- **Data directory**: `~/derivatives/{dataset}-derivatives/meld_graph_v2.2.3/`
- **Config directory**: `~/code/{dataset}-code/meld_graph_v2.2.3/config/`
- **Output location**: `~/derivatives/{dataset}-derivatives/meld_graph_v2.2.3/data/output/predictions_reports/`
- **Container**: `meldproject/meld_graph:v2.2.3`
- **FreeSurfer version**: `7.2.0` (default input - **required**)

> **⚠️ Compatibility Note**: MELD Graph **requires FreeSurfer 7.2.0 or earlier**. It does not work with FreeSurfer 7.3 and above. The default FreeSurfer version for MELD Graph is set to 7.2.0.

> **⚠️ Recommendation**: MELD works best with T1w scans only. If using T1w+FLAIR, interpret results with caution as FLAIR may introduce more false positives.

#### MELD Workflow Overview

MELD Graph has a unique three-step workflow:

1. **Download Weights** (one-time setup): Download pretrained model weights
2. **Harmonization** (optional but recommended): Compute scanner-specific harmonization parameters using 20+ subjects
3. **Prediction**: Run lesion detection on individual subjects

#### Directory Structure

MELD uses a specific directory structure with data in derivatives and config in code:
```
~/derivatives/{dataset}-derivatives/
└── meld_graph_v2.2.3/
    └── data/
        ├── input/
        │   └── sub-{id}/
        │       ├── T1/T1.nii.gz
        │       └── FLAIR/FLAIR.nii.gz (optional)
        └── output/
            ├── predictions_reports/
            ├── fs_outputs/
            └── preprocessed_surf_data/

~/code/{dataset}-code/
└── meld_graph_v2.2.3/
    └── config/
        ├── meld_bids_config.json
        └── dataset_description.json
```

---

#### Step 1: Download Model Weights (One-time Setup)

Before first use, download the MELD Graph pretrained model weights:

```bash
ln2t_tools meld_graph --dataset mydataset --download-weights
```

This downloads ~2GB of model weights into the MELD data directory.

---

#### Step 2: Harmonization (Optional but Recommended)

Harmonization adjusts for scanner/sequence differences and improves prediction accuracy.

**Requirements**:
- At least 20 subjects from the same scanner/protocol
- Harmonization code (e.g., `H1`, `H2`) to identify this scanner
- BIDS `participants.tsv` file with demographic data (see below)

**Demographics Data**:

ln2t_tools automatically creates the MELD-compatible demographics file from your BIDS dataset's `participants.tsv`. The `participants.tsv` file should contain:

Required columns:
- `participant_id`: Subject ID (e.g., sub-001)
- `age` (or `Age`): Numeric age value
- `sex` (or `Sex`, `gender`, `Gender`): M/F or male/female

Optional columns:
- `group`: patient or control (defaults to 'patient' if missing)

Example `participants.tsv`:
```tsv
participant_id	age	sex	group
sub-001	25	M	patient
sub-002	28	F	control
sub-003	32	M	patient
```

**Compute harmonization parameters** (demographics file auto-generated):
```bash
ln2t_tools meld_graph --dataset mydataset \
  --participant-label 01 02 03 ... 20 \
  --harmonize \
  --harmo-code H1
```

The demographics CSV is automatically generated from `participants.tsv`. If you need to inspect or customize it, it will be created at:
```
~/derivatives/{dataset}-derivatives/meld_graph_v2.2.3/demographics_H1.csv
```

The demographics CSV format:
```csv
ID,Harmo code,Group,Age at preoperative,Sex
sub-001,H1,patient,25,male
sub-002,H1,control,28,female
sub-003,H1,patient,32,male
```

This runs FreeSurfer segmentation, extracts features, and computes harmonization parameters. Results saved in `preprocessed_surf_data/`.

> **Note**: This step needs to be run only once per scanner. You can reuse the harmonization parameters for all future subjects from the same scanner.

---

#### Step 3: Prediction - Run Lesion Detection

Once setup is complete, run predictions on individual subjects.

##### Basic Prediction (without harmonization)

```bash
# Single subject
ln2t_tools meld_graph --dataset mydataset --participant-label 01

# Multiple subjects
ln2t_tools meld_graph --dataset mydataset --participant-label 01 02 03
```

##### Prediction with Harmonization

```bash
ln2t_tools meld_graph --dataset mydataset \
  --participant-label 01 \
  --harmo-code H1
```

##### Using Precomputed FreeSurfer Outputs

If you already have FreeSurfer recon-all outputs:

```bash
ln2t_tools meld_graph --dataset mydataset \
  --participant-label 01 \
  --use-precomputed-fs \
  --fs-version 7.2.0
```

This will:
- Look for FreeSurfer outputs in `~/derivatives/{dataset}-derivatives/freesurfer_7.2.0/`
- Bind them to `/data/output/fs_outputs` in the container
- Automatically skip the FreeSurfer segmentation step
- Use the existing FreeSurfer surfaces for feature extraction

##### Skip Feature Extraction (Use Existing MELD Features)

If MELD features (`.sm3.mgh` files) are already extracted from a previous MELD run and you only want to rerun prediction:

```bash
ln2t_tools meld_graph --dataset mydataset \
  --participant-label 01 \
  --skip-feature-extraction
```

> **Important**: `--skip-feature-extraction` tells MELD to skip computing surface features (`.sm3.mgh` files). Use this only when those files already exist from a previous MELD run.

> **Note**: When using `--use-precomputed-fs`, MELD automatically detects existing FreeSurfer outputs and skips recon-all, but still runs feature extraction to create `.sm3.mgh` files. Don't use `--skip-feature-extraction` unless those feature files already exist.

---

#### Complete Example Workflow

```bash
# 1. Download weights (one-time)
ln2t_tools meld_graph --dataset epilepsy_study --download-weights

# 2. Compute harmonization with 25 subjects (one-time per scanner)
#    Demographics automatically created from participants.tsv
ln2t_tools meld_graph --dataset epilepsy_study \
  --participant-label 01 02 03 04 05 06 07 08 09 10 \
                        11 12 13 14 15 16 17 18 19 20 \
                        21 22 23 24 25 \
  --harmonize \
  --harmo-code H1

# 3. Run prediction on new patient with harmonization
ln2t_tools meld_graph --dataset epilepsy_study \
  --participant-label 26 \
  --harmo-code H1

# 4. Run prediction using precomputed FreeSurfer
ln2t_tools meld_graph --dataset epilepsy_study \
  --participant-label 27 \
  --use-precomputed-fs \
  --fs-version 7.2.0 \
  --harmo-code H1
```

---

#### Output Files

Results are saved in:
```
~/derivatives/{dataset}-derivatives/meld_graph_v2.2.3/data/output/predictions_reports/sub-{id}/
├── predictions/
│   ├── predictions.nii.gz           # Lesion probability map in native space
│   └── reports/
│       ├── {id}_prediction.pdf      # Visual report with inflated brain
│       ├── {id}_saliency.pdf        # Model attention maps
│       └── {id}_mri_slices.pdf      # Predictions on MRI slices
└── features/
    └── {id}.hdf5                    # Extracted surface features
```

---

## Instance Management

ln2t_tools includes built-in safeguards to prevent resource overload:

- **Default limit**: Maximum 10 parallel instances
- **Lock files**: Stored in `/tmp/ln2t_tools_locks/` with detailed JSON metadata
- **Automatic cleanup**: Removes stale lock files from terminated processes
- **Graceful handling**: Shows helpful messages when limits are reached

Each instance creates a lock file with:
- Process ID (PID)
- Dataset name(s)
- Tool(s) being run
- Participant labels
- Hostname
- Username
- Start time

## Data Import

ln2t_tools includes import utilities to convert source data to BIDS format. For comprehensive documentation on all import datatypes (DICOM, MRS, Physio, MEG), see the [Data Import Guide](docs/data_import.md).

Supported import datatypes:
- **DICOM**: Convert DICOM files to BIDS using dcm2bids with optional defacing
- **MRS**: Convert MRS data to BIDS using spec2nii
- **Physio**: Convert GE physiological monitoring data to BIDS using phys2bids
- **MEG**: Convert MEG data with MaxFilter derivatives and BIDS-compliant metadata

Each datatype import uses a dedicated configuration file, located by default in the source data folder.

---

## Developer Documentation

For detailed guides on extending `ln2t_tools` and advanced topics, see the [docs/](docs/index.md) folder:

- [Adding a New Tool](docs/adding_new_tool.md) - Complete guide to developing and integrating new neuroimaging pipelines, including custom Apptainer recipes

---
