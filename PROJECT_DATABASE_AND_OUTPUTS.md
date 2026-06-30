# Database and Output Map

This is the project map for the current paper. Anything not needed by the
paper pipeline has been moved to `archive/`.

## Current Paper Pipeline

The current paper analyses are run by `analysis_2`.

- Input database: `data/FINAL_DATABASE_RECALCULATED_MINEFIELD.xlsx`
- Input sheet: `Foglio1`
- Configuration: `analysis_2/config.py`
- Run command: `python analysis_2/run_all.py`
- Official paper outputs: `analysis_2/output/`
- Paper summary: `analysis_2/analysis_summary.md`
- Paper document: `articles_and_documents/chess_scientific_article.qmd`
- Rendered HTML: `articles_and_documents/chess_scientific_article.html`

`analysis_2/config.py` is the source of truth for which database is used by the
paper. At the moment it points to `data/FINAL_DATABASE_RECALCULATED_MINEFIELD.xlsx`.

## What Stayed Outside Archive

| Path | Role |
|---|---|
| `analysis_2/` | Official paper analysis pipeline. |
| `analysis_2/output/` | Generated official paper outputs. |
| `articles_and_documents/` | Paper manuscript and rendered HTML. |
| `data/FINAL_DATABASE_RECALCULATED_MINEFIELD.xlsx` | Final database used by the paper. |
| `data/README.md` | Short note on the final database. |
| `PROJECT_DATABASE_AND_OUTPUTS.md` | This map. |

## What Was Archived

| Archive path | Contents |
|---|---|
| `archive/legacy_analysis/analysis/` | Older analysis scripts and the Minefield scoring code used to create/audit the database. Not run by the paper pipeline. |
| `archive/database_sources_and_audits/` | Original database, raw Minefield files, scoring configuration, and full best-available Minefield audit database. |
| `archive/exploratory_output/` | Legacy outputs and exploratory/sensitivity outputs, including Raven, CBT, age-group, class, and mixed-model checks. |
| `archive/data_old/` | Older data folder kept for traceability. |
| `archive/render_intermediates/` | Quarto/LaTeX intermediate files not needed by the paper. |

## How the Final Paper Database Was Created

The paper database is:

`data/FINAL_DATABASE_RECALCULATED_MINEFIELD.xlsx`

It was created from the original source database:

`archive/database_sources_and_audits/FINAL_DATABASE.xlsx`

The Minefield route-efficiency values were recalculated using:

- raw Minefield files in `archive/database_sources_and_audits/Minefield_raw/`;
- trial configuration in `archive/database_sources_and_audits/configuration_trial.xlsx`;
- scoring code in `archive/legacy_analysis/analysis/minefield_scoring/scoring.py`.

The scoring step preserved the original 104-column database schema. Only four
historical Minefield route-efficiency columns could be updated:

- `PLANNING_PERC_PRE`
- `PLANNING_PERC_POST`
- `PWM_PERC_PRE`
- `PWM_PERC_POST`

For those four columns, the rule was:

1. use the recalculated value from raw Minefield data when available;
2. if raw data were missing, retain the historical/original database value;
3. leave every other historical column unchanged.

The larger audit database
`archive/database_sources_and_audits/FINAL_DATABASE_MINEFIELD_FULL_BEST_AVAILABLE.xlsx`
was created only for checking completeness and provenance. It is not used by
the paper pipeline.

## Analyses Performed by `analysis_2`

The official pipeline is fully rerunnable with:

```powershell
python analysis_2\run_all.py
```

The stages are:

1. `prepare_data.py`: loads `Foglio1`, standardizes known column-name variants,
   creates group labels, ABAS/BRIEF totals, Minefield composites, and log
   transforms for time variables.
2. `descriptives.py`: writes descriptive statistics and missingness summaries.
3. `baseline.py`: checks baseline group balance.
4. `pre_age_sex.py`: tests cognitive/Minefield PRE measures and baseline
   ABAS/BRIEF questionnaire measures for age and sex differences using Welch
   independent-samples t-tests with Benjamini-Hochberg FDR correction.
5. `correlations.py`: computes Pearson and Spearman correlations with FDR
   correction.
6. `training_effect.py`: tests training effects across PRE/POST outcomes with
   age-adjusted linear models in long format. For each outcome, the primary
   model is `score ~ time * group + age`, with standard errors clustered by
   participant. The time-by-group term tests whether change differs between the
   experimental and control groups. The module also writes within-group tests,
   change-score comparisons, and plots.
7. `effectiveness.py`: computes bounded treatment-effectiveness scores for
   outcomes with confirmed theoretical limits, plus group comparisons and
   age-adjusted comparisons.
8. `predictors.py`: tests whether ABAS-II and BRIEF-2 variables predict PRE
   cognitive outcomes with age-adjusted standardized linear models
   (`PRE outcome_z ~ questionnaire predictor_z + age_z`). The workbook also
   keeps exploratory treatment-effectiveness predictor and moderation models
   for audit.
9. `pca_analysis.py`: runs pooled PRE/POST PCA for Minefield domains using
   standardized features, median imputation, and the predefined missingness
   rule.
10. `run_all.py`: cleans and rebuilds `analysis_2/output/`, writes
    `analysis_2/analysis_summary.md`, and creates
    `analysis_2/output/run_manifest.xlsx` with file hashes and environment
    details.

## Rules for Future Work

1. Do not overwrite `data/FINAL_DATABASE_RECALCULATED_MINEFIELD.xlsx` unless
   we intentionally create a new paper database.
2. Do not change `analysis_2/config.py` to another database until that database
   has been audited and explicitly promoted.
3. Keep official paper analyses in `analysis_2/`.
4. Put new exploratory checks in `archive/exploratory_output/` or a clearly
   named new archive subfolder.
5. If an exploratory check becomes part of the paper, promote it into
   `analysis_2/` and document the change here.
