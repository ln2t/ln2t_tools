"""Utilities for creating MELD demographics files from BIDS participants.tsv."""

import logging
from pathlib import Path
from typing import List, Optional
import pandas as pd

logger = logging.getLogger(__name__)


def create_meld_demographics_from_participants(
    participants_tsv: Path,
    participant_labels: List[str],
    harmo_code: str,
    output_path: Path
) -> Optional[Path]:
    """Create MELD-compatible demographics CSV from BIDS participants.tsv.
    
    MELD requires demographics file with columns:
    - ID: Subject ID (e.g., sub-01)
    - Harmo code: Harmonization code (e.g., H1, H2)
    - Group: patient or control
    - Age at preoperative: Age (numeric)
    - Sex: male or female
    
    BIDS participants.tsv typically contains:
    - participant_id: Subject ID
    - age: Age (may need conversion)
    - sex: Sex (may be M/F or male/female)
    - group: Group (may be patient/control or other labels)
    
    Args:
        participants_tsv: Path to BIDS participants.tsv file
        participant_labels: List of participant IDs to include (without 'sub-' prefix)
        harmo_code: Harmonization code (e.g., 'H1', 'H2')
        output_path: Where to save the demographics CSV
        
    Returns:
        Path to created demographics file, or None if failed
    """
    if not participants_tsv.exists():
        logger.error(f"participants.tsv not found: {participants_tsv}")
        return None
    
    try:
        # Read participants.tsv
        df = pd.read_csv(participants_tsv, sep='\t')
        logger.info(f"Loaded participants.tsv with {len(df)} subjects")
        logger.info(f"Available columns: {', '.join(df.columns)}")
        
        # Filter to requested participants
        # participants.tsv has 'participant_id' with 'sub-' prefix
        requested_ids = [f"sub-{label}" for label in participant_labels]
        df_filtered = df[df['participant_id'].isin(requested_ids)].copy()
        
        if len(df_filtered) == 0:
            logger.error(f"No participants found in participants.tsv matching: {requested_ids}")
            return None
        
        if len(df_filtered) < len(requested_ids):
            missing = set(requested_ids) - set(df_filtered['participant_id'])
            logger.warning(f"Some participants not found in participants.tsv: {missing}")
        
        # Check for required columns and map them
        demographics = pd.DataFrame()
        
        # ID column (required)
        demographics['ID'] = df_filtered['participant_id']
        
        # Harmo code (same for all)
        demographics['Harmo code'] = harmo_code
        
        # Group column
        if 'group' in df_filtered.columns:
            demographics['Group'] = df_filtered['group'].str.lower()
            # Ensure values are 'patient' or 'control'
            valid_groups = demographics['Group'].isin(['patient', 'control'])
            if not valid_groups.all():
                invalid = demographics.loc[~valid_groups, 'Group'].unique()
                logger.warning(
                    f"Invalid group values found: {invalid}. "
                    f"MELD expects 'patient' or 'control'. Defaulting to 'patient'."
                )
                demographics.loc[~valid_groups, 'Group'] = 'patient'
        else:
            logger.warning(
                "Column 'group' not found in participants.tsv. "
                "Defaulting all participants to 'patient'."
            )
            demographics['Group'] = 'patient'
        
        # Age column
        age_col = None
        for possible_age_col in ['age', 'Age', 'age_at_preoperative', 'Age at preoperative']:
            if possible_age_col in df_filtered.columns:
                age_col = possible_age_col
                break
        
        if age_col:
            demographics['Age at preoperative'] = pd.to_numeric(
                df_filtered[age_col], errors='coerce'
            )
            # Check for NaN values
            if demographics['Age at preoperative'].isna().any():
                missing_age = demographics[demographics['Age at preoperative'].isna()]['ID']
                logger.error(
                    f"Missing or invalid age values for: {missing_age.tolist()}. "
                    f"Age is required for MELD harmonization."
                )
                return None
        else:
            logger.error(
                "Age column not found in participants.tsv. "
                f"Looked for: 'age', 'Age', 'age_at_preoperative'. "
                f"Available columns: {df_filtered.columns.tolist()}"
            )
            return None
        
        # Sex column
        sex_col = None
        for possible_sex_col in ['sex', 'Sex', 'gender', 'Gender']:
            if possible_sex_col in df_filtered.columns:
                sex_col = possible_sex_col
                break
        
        if sex_col:
            # Normalize sex values to 'male' or 'female'
            sex_mapping = {
                'M': 'male', 'm': 'male', 'male': 'male', 'Male': 'male',
                'F': 'female', 'f': 'female', 'female': 'female', 'Female': 'female'
            }
            demographics['Sex'] = df_filtered[sex_col].map(sex_mapping)
            
            # Check for invalid values
            if demographics['Sex'].isna().any():
                invalid_sex = df_filtered.loc[demographics['Sex'].isna(), ['participant_id', sex_col]]
                logger.error(
                    f"Invalid sex values found:\n{invalid_sex}\n"
                    f"MELD expects 'male' or 'female' (or M/F)."
                )
                return None
        else:
            logger.error(
                "Sex column not found in participants.tsv. "
                f"Looked for: 'sex', 'Sex', 'gender', 'Gender'. "
                f"Available columns: {df_filtered.columns.tolist()}"
            )
            return None
        
        # Save demographics file
        demographics.to_csv(output_path, index=False)
        logger.info(f"Created MELD demographics file: {output_path}")
        logger.info(f"Demographics file contains {len(demographics)} subjects")
        
        # Show summary
        logger.info(f"Group distribution: {demographics['Group'].value_counts().to_dict()}")
        logger.info(f"Sex distribution: {demographics['Sex'].value_counts().to_dict()}")
        logger.info(f"Age range: {demographics['Age at preoperative'].min():.1f} - {demographics['Age at preoperative'].max():.1f}")
        
        return output_path
        
    except Exception as e:
        logger.error(f"Error creating demographics file: {e}", exc_info=True)
        return None


def validate_meld_demographics(demographics_path: Path) -> bool:
    """Validate that demographics file has required MELD columns.
    
    Args:
        demographics_path: Path to demographics CSV file
        
    Returns:
        True if valid, False otherwise
    """
    required_columns = ['ID', 'Harmo code', 'Group', 'Age at preoperative', 'Sex']
    
    try:
        df = pd.read_csv(demographics_path)
        
        # Check for required columns
        missing_cols = set(required_columns) - set(df.columns)
        if missing_cols:
            logger.error(f"Demographics file missing required columns: {missing_cols}")
            return False
        
        # Validate values
        if df['Group'].isna().any() or not df['Group'].isin(['patient', 'control']).all():
            logger.error("Group column must contain only 'patient' or 'control'")
            return False
        
        if df['Age at preoperative'].isna().any():
            logger.error("Age at preoperative column contains missing values")
            return False
        
        if df['Sex'].isna().any() or not df['Sex'].isin(['male', 'female']).all():
            logger.error("Sex column must contain only 'male' or 'female'")
            return False
        
        logger.info(f"Demographics file validated successfully: {len(df)} subjects")
        return True
        
    except Exception as e:
        logger.error(f"Error validating demographics file: {e}")
        return False
