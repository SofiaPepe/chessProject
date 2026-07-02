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
- `output/tables/` paper-ready CSV and Markdown tables
- `output/run_manifest.xlsx`

## Analysis Scope

- Participants: all valid IDs from `data/FINAL_DATABASE_RECALCULATED_MINEFIELD.xlsx`
- Outcomes: PRE cognitive, Minefield, and derived PRE outcomes only
- Predictors: ABAS-II and BRIEF-2 subscales, indices, and totals
- Primary significance rule: Benjamini-Hochberg FDR q < .05
- Primary regression: standardized PRE outcome predicted by standardized
  questionnaire score, adjusted for standardized age

