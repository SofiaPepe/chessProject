# ABAS/BRIEF Navigation Paper

This sub-project contains the baseline-only cross-sectional analyses for the
separate ABAS/BRIEF and navigation paper.

The analysis treats all children as one baseline sample. It uses only PRE
outcomes and ignores training group, POST scores, and PRE-to-POST change.

## Run

From the repository root:

```powershell
python abas_brief_navigation_paper\analysis\run_analysis.py
```

Generated files are written to:

`abas_brief_navigation_paper/output/`

The paper draft is:

`abas_brief_navigation_paper/paper/abas_brief_navigation_paper.qmd`

## Main Outputs

- `output/00_data/baseline_pre_dataset.xlsx`
- `output/01_descriptives/descriptives.xlsx`
- `output/02_correlations/abas_brief_pre_correlations.xlsx`
- `output/03_regressions/abas_brief_pre_regressions.xlsx`
- `output/04_totals_subscales/totals_subscales_models.xlsx`
- `output/tables/dedicated_totals_subscales_summary.md`
- `output/tables/` paper-ready CSV and Markdown tables
- `output/run_manifest.xlsx`

## Analysis Scope

- Participants: all valid IDs from `data/FINAL_DATABASE_RECALCULATED_MINEFIELD.xlsx`
- Outcomes: PRE cognitive, Minefield, and derived PRE outcomes only
- Predictors: ABAS-II and BRIEF-2 subscales, indices, and totals
- Primary significance rule: Benjamini-Hochberg FDR q < .05
- Primary regression: standardized PRE outcome predicted by standardized
  questionnaire score, adjusted for standardized age

## Dedicated Total and Subscale Models

The dedicated analysis uses 9 user-selected non-Raven PRE outcomes: Corsi
forward/backward span, Tower of London accuracy/rule violations, Minefield WM
accuracy, Planning accuracy/EFF, and PWM accuracy/EFF. Its primary
sample excludes the two children flagged by the age-specific Raven screening
cutoffs (`n = 99`), while the full `n = 101` sample is retained as a
sensitivity analysis. Every model is fitted on identical complete cases with
and without Raven PRE accuracy as a covariate.

The prespecified predictor blocks are complete-case ABAS and BRIEF totals,
eight standard ABAS scales, nine standard BRIEF scales, and the BRIEF BRI,
ERI, and CRI indices. ABAS `suppongo` variables, supplemental totals, Raven
outcomes, raw/log time duplicates, and redundant Minefield composites are excluded.
The selected `EFF` outcomes are retained and their negative values are explicitly
reported in the outcome audit.
`PLANNING_OST` is excluded because it is nearly redundant with Planning accuracy;
`PWM_OST` is excluded because the raw obstacle count is strongly dependent on the
number of trials completed. Its distribution remains documented as a supplemental
audit.
Benjamini-Hochberg FDR correction is applied separately within each block.

