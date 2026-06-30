# Archive

This folder contains material that is not used directly by the current paper
pipeline. It is kept for traceability and possible future audit.

## Contents

| Folder | Contents |
|---|---|
| `legacy_analysis/analysis/` | Older analysis scripts and Minefield scoring code. |
| `database_sources_and_audits/` | Original database, raw Minefield files, scoring configuration, and full Minefield audit database. |
| `exploratory_output/` | Legacy outputs and exploratory/sensitivity checks. |
| `data_old/` | Older data folder. |
| `render_intermediates/` | Quarto/LaTeX intermediate files not needed by the paper. |

## Important

The current paper does not read files from `archive/`. The paper reads:

`data/FINAL_DATABASE_RECALCULATED_MINEFIELD.xlsx`

through:

`analysis_2/config.py`

Archived files are useful only for reconstructing how the final database was
created, checking old exploratory results, or recovering previous analysis
attempts.
