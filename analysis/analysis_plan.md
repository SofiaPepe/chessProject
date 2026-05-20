# Analysis plan

## Research question

The project compares two groups of children:

- experimental group: children who completed the chess/training protocol;
- control group: children who did not complete the training during the same interval.

The main hypothesis is that the experimental group improved more from pre-test to post-test than the control group across cognitive, planning, working-memory, adaptive-functioning, and executive-function variables.

## Data structure

The official source database is:

- `data/FINAL_DATABASE.xlsx`

Old or duplicate database files are stored in `data_old/`, which is ignored by Git. Generated analysis datasets, tables, and figures should stay in `output/`, which is also ignored by Git.

The official dataset should contain one row per participant and paired pre/post columns for each repeated measure, for example:

- `VARIABLE_PRE`
- `VARIABLE_POST`
- group column: `group`
- participant ID: `ID`
- covariates: age, sex, class/grade, section where available.

Current script groups:

- `analysis/descriptives`: cleaning, composites, descriptive statistics;
- `analysis/repeated_anova/training_effect`: pre/post group x time analyses;
- `analysis/planning_minefield/training_effect`: Planning Minefield pre/post effects;
- `analysis/planning_minefield/regressions`: predictor/regression models;
- `analysis/correlations`: correlation analyses;
- `analysis/pca`: PCA and PCA-based models.

Predictor/regression outputs should be kept separate from training-effect outputs. Planning Minefield predictor models are written to:

- `output/predictors/planning_minefield/`

`data/FINAL_DATABASE.xlsx` is the only database. Composite variables are generated in memory by `analysis/descriptives/add_composites.py` when analysis scripts run, and should not be exported as a second database workbook.

## 1. Baseline checks

Before testing training effects, check whether the experimental and control groups differed at baseline.

### Sample comparability

Run group comparisons for:

- age;
- sex;
- class/grade;
- section/school, if relevant;
- Raven or other general cognitive screening variables;
- every outcome at pre-test.

Recommended tests:

- numeric baseline variables: independent-samples t-test if assumptions are acceptable; Mann-Whitney U as sensitivity check if distributions are skewed;
- categorical variables: chi-square test or Fisher exact test when expected counts are small;
- report effect sizes, not only p-values: Cohen's d or Hedges g for numeric variables; Cramer's V for categorical variables.

Important output:

- mean and SD by group;
- median and IQR by group;
- p-value;
- effect size;
- flag variables with meaningful baseline imbalance.

Decision rule:

- If groups differ at baseline on an outcome, do not interpret raw post-pre change alone.
- Prefer a model that estimates group x time while accounting for baseline/covariates, or an ANCOVA-style model predicting post-test from group and pre-test.

## 2. Pre/post training effect

This has already been partly done, but it can be improved by making the primary model explicit and consistent across variables.

### Primary model

For each repeated variable, use a group x time model:

```text
score ~ group + time + group:time
```

The key result is the `group:time` interaction:

- significant positive interaction: experimental group improved more than control;
- significant negative interaction: experimental group worsened or improved less than control;
- non-significant interaction: no evidence that improvement differed by group.

Recommended implementation:

- use a long-format dataset with one row per participant per time point;
- use mixed models with participant as random intercept when possible;
- use linear regression / repeated-measures ANOVA as fallback if mixed model fails;
- include age, sex, and class as covariates in sensitivity analyses.

### Secondary checks

Also report:

- within-group pre/post tests for experimental group;
- within-group pre/post tests for control group;
- post-hoc contrasts only when the interaction is significant;
- effect sizes for change within each group;
- correction for multiple comparisons, for example FDR Benjamini-Hochberg.

### Improvements to existing scripts

The current pre/post analyses can be improved by:

- producing one standardized summary table for all variables;
- adding baseline imbalance flags;
- adding effect sizes for group x time;
- clearly separating primary outcomes from exploratory outcomes;
- adding FDR-corrected p-values across families of tests, not across unrelated analyses mixed together.

## 3. Treatment effectiveness

The article-style effectiveness score is useful because it normalizes each child's improvement by the amount of improvement still possible from their baseline score.

For variables where higher scores are better:

```text
effectiveness = ((post_score - pre_score) / (maximum_possible_score - pre_score)) * 100
```

Example:

```text
maximum_possible_score = 10
pre_score = 6
post_score = 8
effectiveness = ((8 - 6) / (10 - 6)) * 100 = 50%
```

This means the child achieved 50% of the improvement they could still theoretically achieve.

### Variables where lower scores are better

For time, errors, rule violations, or other outcomes where lower values indicate improvement, use the mirrored formula:

```text
effectiveness = ((pre_score - post_score) / (pre_score - minimum_possible_score)) * 100
```

This requires the minimum possible score.

### Required Variable Metadata

Implemented metadata:

- `analysis/shared/variable_metadata.csv`
- `analysis/shared/composite_metadata.csv`

Included for treatment effectiveness: `CBT_F_SPAN`, `CBT_B_SPAN`, `TOL_ACC`, `Raven_ACC`, `WM_ACC`, `PLANNING_ACC`, `PWM_ACC`, `PLANNING_COMPOSITE`, `PWM_COMPOSITE`, `planning_tiles_extra`, `pwm_tiles_extra`.

Composite Planning/PWM scores are generated in memory by `analysis/descriptives/add_composites.py` and documented in `analysis/shared/composite_metadata.csv`. They combine accuracy and path efficiency on a 0-100 scale:

```text
accuracy_component = (ACC / 16) * 100
tiles_component = ((50 - tiles_extra) / 50) * 100
composite = mean(accuracy_component, tiles_component)
```

The composite requires both valid components. `tiles_extra = 0` is optimal, and values outside 0-50 are invalid.

General validity rules are stored in the same metadata file. For tile-difference variables, values below `0` or above `50` are invalid and must be excluded consistently across analyses.

Excluded for now: response-time variables and all variables without confirmed scoring bounds/direction.

To calculate treatment effectiveness properly, create a scoring table like this:

| variable | pre_col | post_col | improvement_direction | min_possible | max_possible | notes |
| --- | --- | --- | --- | --- | --- | --- |
| CBT_F_SPAN | `CBT_F_SPAN_PRE` | `CBT_F_SPAN_POST` | higher_better | 0 | 9 | confirm max |
| PLANNING_ACC | `PLANNING_ACC_PRE` | `PLANNING_ACC_POST` | higher_better | 0 | TBD | confirm |
| TOL_TE | `TOL_TE_PRE` | `TOL_TE_POST` | lower_better | 0 | TBD | time/latency |
| PWM_MATT_DIFF | `pwm_mattonelle_diff_pre` | `pwm_mattonelle_diff_post` | lower_or_higher_TBD | TBD | TBD | define meaning |

Fields:

- `higher_better`: improvement is post minus pre;
- `lower_better`: improvement is pre minus post;
- `min_possible`: theoretical minimum score;
- `max_possible`: theoretical maximum score.

### If theoretical max/min is unknown

Best option:

- use the real theoretical maximum/minimum from the test manual or scoring rules.

Acceptable exploratory option:

- use the observed sample maximum/minimum, but label it clearly as sample-normalized effectiveness.

Better sensitivity option:

- run both versions where possible:
  - theoretical effectiveness;
  - observed-range effectiveness.

Do not silently use the observed maximum as if it were the real maximum. It changes the interpretation and can make results sample-dependent.

### Edge cases

Handle these explicitly:

- if `maximum_possible_score == pre_score` for a higher-better variable, the child has no room to improve; effectiveness is undefined or should be marked as ceiling;
- if `minimum_possible_score == pre_score` for a lower-better variable, the child has no room to improve; mark as floor;
- effectiveness can be negative if the child worsened;
- effectiveness can exceed 100% if post-test exceeds the declared maximum or if scoring metadata is wrong;
- inspect outliers before group comparison.

### Group comparison of effectiveness

After calculating effectiveness per participant and variable:

Primary comparison:

```text
effectiveness ~ group
```

Recommended tests:

- independent-samples t-test plus Hedges g;
- Mann-Whitney U as sensitivity check;
- linear regression with covariates if baseline/sample imbalance exists:

```text
effectiveness ~ group + age + sex + class
```

Report:

- mean effectiveness by group;
- SD and confidence interval;
- group difference;
- p-value;
- effect size;
- FDR-corrected q-value across variables.

## 4. Regression and predictor analyses

Use regressions to ask whether baseline abilities or questionnaire scores predict:

- baseline Planning/PWM performance;
- post-test Planning/PWM performance;
- pre/post sum or change;
- treatment effectiveness, once computed.

Recommended models:

```text
outcome ~ predictor + group + age + sex
```

For moderation:

```text
outcome ~ predictor * group + age + sex
```

For effectiveness:

```text
effectiveness ~ predictor + group + age + sex
```

Important:

- keep predictor analyses exploratory unless hypotheses are specified in advance;
- correct for multiple testing;
- avoid interpreting many isolated p-values without effect sizes and confidence intervals.

## 5. Suggested analysis sequence

1. Confirm and freeze variable dictionary.
2. Confirm scoring metadata for max/min and improvement direction.
3. Regenerate composite variables and cleaned dataset.
4. Run baseline comparability checks.
5. Run primary group x time models.
6. Improve existing pre/post tables with effect sizes and FDR correction.
7. Calculate treatment effectiveness for variables with valid max/min metadata. Done for the user-confirmed variables in `analysis/training_effect/treatment_effectiveness.py`.
8. Compare effectiveness between groups. Done in `output/training_effect/treatment_effectiveness/treatment_effectiveness_results.xlsx`.
9. Run exploratory regressions and moderation models.
10. Export one final results workbook per analysis family.

## 6. Files to add next

Recommended next implementation files:

- `analysis/shared/variable_metadata.csv`
- `analysis/descriptives/baseline_checks.py`
- `analysis/training_effect/treatment_effectiveness.py`
- `analysis/shared/statistics_utils.py`

The current next step is predictor/moderation analysis using the treatment-effectiveness scores, after deciding which baseline predictors should be prioritized.
