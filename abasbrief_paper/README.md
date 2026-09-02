# ABAS-II/BRIEF-2 and Visuospatial Abilities Paper

This self-contained subproject examines whether teacher-rated adaptive
functioning (ABAS-II) and everyday executive functioning (BRIEF-2) are
associated with children's baseline visuospatial abilities.

The analysis is cross-sectional and PRE-only. Raven Coloured Progressive
Matrices are used only to screen the primary sample. Training group, POST
scores, change scores, Raven covariate models, and sensitivity analyses are not
part of this pipeline.

## Run in R

From the `chessProject` repository root:

```powershell
Rscript abasbrief_paper\scripts_r\run_analysis.R
Rscript abasbrief_paper\scripts_r\render_paper.R
```

On this computer, if `Rscript` has not been added to `PATH`, use:

```powershell
& "C:\Program Files\R\R-4.4.2\bin\Rscript.exe" abasbrief_paper\scripts_r\run_analysis.R
& "C:\Program Files\R\R-4.4.2\bin\Rscript.exe" abasbrief_paper\scripts_r\render_paper.R
```

The first command generates aggregate statistical outputs and figures without
exporting participant-level records or IDs. The second command renders the
English Methods-and-Results paper to DOCX and HTML with Quarto. Close the DOCX
in Word before running the rendering command.

Required R packages are `readxl`, `openxlsx`, `sandwich`, `ggplot2`, and
`digest`.

## Python/R parity verification

The original Python implementation is retained unchanged in `scripts/` as an
independent reference. To run both implementations and compare the five CSV
outputs, ten stable workbook sheets, and six paper Markdown files:

```powershell
Rscript abasbrief_paper\scripts_r\verify_parity.R
```

The verifier leaves the R-generated outputs in place and writes
`output/r_python_parity_report.csv`. Numeric equivalence is checked to a
tolerance of `1e-8`; the paper Markdown files must match exactly.

## Analysis

- Source: `data/FINAL_DATABASE_RECALCULATED_MINEFIELD.xlsx`, sheet `Foglio1`
- Source sample: 101 children
- Raven-screened sample: 99 children
- Outcomes: nine selected PRE visuospatial/cognitive measures
- Predictors: complete ABAS-II/BRIEF-2 totals, standard subscales, and BRIEF-2 indices
- Model: `outcome_z ~ questionnaire_predictor_z + age_z`
- Estimation: OLS with HC3 robust standard errors
- Multiple testing: Benjamini–Hochberg FDR within five prespecified blocks

## Main outputs

- `output/analysis_results.xlsx`
- `output/analysis_summary.md`
- `output/tables/`
- `figures/primary_forest_plot.*`
- `figures/significant_beta_heatmap.*`
- `paper/abasbrief_paper.docx`
- `paper/abasbrief_paper.html`

## Tests

```powershell
Rscript abasbrief_paper\scripts_r\tests\test_analysis.R
```

The former Python tests remain available for independent validation:

```powershell
python -m unittest discover -s abasbrief_paper\scripts\tests -v
```
