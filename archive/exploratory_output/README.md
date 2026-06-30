# Output Directory

This directory contains Minefield audit outputs, legacy outputs, and
exploratory/sensitivity checks. It is not the primary output folder for the
current paper pipeline.

For current paper results, use:

`analysis_2/output/`

## Current Folders

| Folder | Status | Meaning |
|---|---|---|
| `minefield_scoring/` | Audit/scoring | Minefield raw recalculation outputs and database audit files. |
| `raven_distribution/` | Exploratory check | Distribution of Raven scores. |
| `raven_cutoff_exclusion_check/` | Sensitivity check | Excludes participants below Raven age-specific cutoffs. |
| `cbt_cutoff_exclusion_check/` | Sensitivity check | CBT low-score exclusion check. |
| `age_5_as_6_sensitivity/` | Sensitivity check | Treats 5-year-olds as part of the 6-year-old group. |
| `exclude_age_5_sensitivity/` | Sensitivity check | Excludes 5-year-olds. |
| `raven_covariate_sensitivity/` | Sensitivity check | Adds Raven as a covariate. |
| `mixed_model_raven_age/` | Sensitivity check | Mixed model with Raven and age. |
| `mixed_model_sensitivity/` | Sensitivity check | Mixed model sensitivity outputs. |
| `class_covariate_sensitivity/` | Sensitivity check | Class/cluster experiment. |
| `training_effect/`, `descriptives/`, `correlations/`, `pca/`, `predictors/`, `jamovi/` | Legacy output | Earlier analysis outputs kept for traceability. Prefer `analysis_2/output/` for the current paper. |

## Rule

Files here are not official paper outputs unless they are explicitly cited in
`PROJECT_DATABASE_AND_OUTPUTS.md` or promoted into the `analysis_2` pipeline.
