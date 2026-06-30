# Analysis 2 summary

## Input

- Database: `data\FINAL_DATABASE_RECALCULATED_MINEFIELD.xlsx`
- SHA-256: `7668a89406c7836cd62b8b4694fcddd906910f9cbc5dcd30aa0a63edba9385c0`
- Participants: 101
- Minefield scores: original database measures with Planning and WM-Planning route efficiency recalculated where raw data are available

## Analyses completed

- PRE/POST variables tested: 45
- Group x time interactions significant after FDR: 0
- Age-adjusted group x time interactions significant after FDR: 0
- Baseline/PRE measures associated with age after FDR: 20
- Baseline/PRE measures differing by sex after FDR: 0
- Effectiveness outcomes: 11
- Effectiveness group comparisons significant after FDR: 0
- PRE outcomes predicted by ABAS/BRIEF after FDR: 24
- Predictor main effects significant after FDR: 17
- Predictor moderation effects significant after FDR: 0
- PCA domains completed: 3
- Correlation pairs tested: 7503
- Spearman correlations significant after FDR: 1366

## Method notes

- Primary training test: linear model on PRE/POST scores with time, group, time x group, and age; standard errors are clustered by participant.
- The time x group term tests whether PRE-to-POST change differs between experimental and control groups after adjusting for age.
- Multiple testing: Benjamini-Hochberg FDR within each result family.
- Minefield composites combine original accuracy with recalculated route-efficiency percentage.
- Effectiveness is calculated only for outcomes with confirmed theoretical bounds.
- PCA is fit on pooled PRE/POST standardized Minefield features; rows with at least 60% observed features are median-imputed.

## Reproducibility

- Runtime: 48.2 seconds
- Run command: `python analysis_2/run_all.py`
- Detailed workbooks and plots are under `analysis_2/output/`.
