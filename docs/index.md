# Documentation Index

This directory contains detailed documentation for `ln2t_tools` developers and advanced users.

## Available Documentation

### [Adding a New Tool](adding_new_tool.md)
Complete step-by-step guide to developing and integrating new neuroimaging pipelines into `ln2t_tools`. Covers:
- Tool architecture and implementation
- Registration and configuration
- Creating custom Apptainer container recipes
- Best practices and advanced features

**Audience**: Tool developers, contributors  
**Time**: 30-60 minutes to fully implement

### [Data Import Guide](data_import.md)
Comprehensive guide to importing and converting source data to BIDS format. Covers:
- DICOM to BIDS conversion with dcm2bids
- MRS data conversion with spec2nii
- Physiological data (GE physio) processing with phys2bids
- MEG data conversion with MaxFilter derivatives and calibration files
- Configuration file setup for each datatype
- Directory structure and naming conventions

**Audience**: Lab administrators, data managers  
**Use when**: Setting up data import pipelines for your lab

---

## Future Documentation

This directory is organized to support growing documentation:

- `developer_guides/` - Advanced development topics
- `user_guides/` - End-user how-to guides
- `troubleshooting/` - Common issues and solutions
- `api/` - API reference for extension developers

---

## Quick Links

- [Main README](../README.md) - Installation, usage, and supported tools
- [Data Organization Guide](../README.md#data-organization) - BIDS folder structure
- [HPC Usage](../README.md#using-hpc) - Running on cluster systems
