from __future__ import annotations

import warnings
import sys
from pathlib import Path

ANALYSIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ANALYSIS_DIR.parents[1]
ANALYSIS_2_ROOT = PROJECT_ROOT / "analysis_2"
if str(ANALYSIS_2_ROOT) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_2_ROOT))

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

from common import fdr_bh, to_numeric, write_workbook
import paper_config as cfg


OUT_DIR = cfg.OUTPUT_ROOT / "04_totals_subscales"
TABLE_DIR = cfg.OUTPUT_ROOT / "tables"

ABAS_STANDARD_SCALES = [
    "ABAS_comm_use",
    "ABAS_fun_acc",
    "ABAS_school_liv",
    "ABAS_Health_saf_sic",
    "ABAS_Leisure",
    "ABAS_Selfcare",
    "ABAS_Selfdirection",
    "ABAS_soc",
]

BRIEF_STANDARD_SCALES = [
    "BRIEF_Inhibit",
    "BRIEF_SelfMonitor",
    "BRIEF_shift",
    "BRIEF_Em_Con",
    "BRIEF_Initiate",
    "BRIEF_wm",
    "BRIEF_plann",
    "BRIEF_TaskMonitor",
    "BRIEF_OrganizMaterial",
]

BRIEF_INDICES = ["BRIEF_BRI", "BRIEF_ERI", "BRIEF_CRI"]

COMPLETE_TOTALS = {
    "ABAS_TOT_complete": ABAS_STANDARD_SCALES,
    "BRIEF_TOT_complete": BRIEF_STANDARD_SCALES,
}

# User-selected PRE outcomes for the dedicated ABAS/BRIEF models. Raven is
# never an outcome. EFF is retained as the absolute tile-difference measure;
# its data-quality characteristics are documented in the outcome dictionary.
CURATED_OUTCOMES = [
    ("CBT_F_SPAN", "CBT_F_SPAN_PRE", "corsi"),
    ("CBT_B_SPAN", "CBT_B_SPAN_PRE", "corsi"),
    ("TOL_ACC", "TOL_ACC_PRE", "tower_of_london"),
    ("TOL_VIO_REG", "TOL_VIO_REG_PRE", "tower_of_london"),
    ("WM_ACC", "WM_ACC_PRE", "minefield_working_memory"),
    ("PLANNING_ACC", "PLANNING_ACC_PRE", "minefield_planning"),
    ("PLANNING_EFF", "PLANNING_EFF_PRE", "minefield_planning"),
    ("PWM_ACC", "PWM_ACC_PRE", "minefield_planning_working_memory"),
    ("PWM_EFF", "PWM_EFF_PRE", "minefield_planning_working_memory"),
]

PREDICTOR_BLOCKS = {
    "totals_separate": list(COMPLETE_TOTALS),
    "abas_subscales": ABAS_STANDARD_SCALES,
    "brief_subscales": BRIEF_STANDARD_SCALES,
    "brief_indices": BRIEF_INDICES,
}

RAVEN_CUTOFFS = {5: 10, 6: 11, 7: 12}


def add_complete_totals_and_screening(dataset: pd.DataFrame) -> pd.DataFrame:
    result = dataset.copy()
    for total, components in COMPLETE_TOTALS.items():
        missing = [column for column in components if column not in result]
        if missing:
            raise KeyError(f"Missing components for {total}: {missing}")
        numeric = result[components].apply(to_numeric)
        result[total] = numeric.sum(axis=1, min_count=len(components))
        result[f"{total}_components_observed"] = numeric.notna().sum(axis=1)

    age = to_numeric(result["age"])
    raven = to_numeric(result["Raven_ACC_PRE"])
    result["raven_screen_cutoff"] = age.map(RAVEN_CUTOFFS)
    result["raven_screen_flag"] = (
        raven.notna()
        & result["raven_screen_cutoff"].notna()
        & raven.le(result["raven_screen_cutoff"])
    )
    result["raven_screen_status"] = np.select(
        [
            age.isna() | raven.isna(),
            result["raven_screen_cutoff"].isna(),
            result["raven_screen_flag"],
        ],
        ["missing_age_or_raven", "age_outside_defined_cutoffs", "flagged"],
        default="passed",
    )
    result["included_primary_n99"] = ~result["raven_screen_flag"]
    return result


def outcome_dictionary(dataset: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for outcome, pre_col, family in CURATED_OUTCOMES:
        if pre_col not in dataset:
            raise KeyError(f"Curated PRE outcome not found: {pre_col}")
        values = to_numeric(dataset[pre_col])
        rows.append(
            {
                "outcome": outcome,
                "pre_col": pre_col,
                "outcome_family": family,
                "n_nonmissing_full": int(values.notna().sum()),
                "transformation": "log" if "_LN" in outcome else "raw",
                "minimum_full": values.min(),
                "maximum_full": values.max(),
                "n_negative_full": int(values.lt(0).sum()),
                "direction": "lower_better" if outcome.endswith(("_OST", "_EFF", "_VIO_REG")) else "higher_better",
            }
        )
    result = pd.DataFrame(rows)
    if result["outcome"].str.contains("RAVEN", case=False).any():
        raise RuntimeError("Raven outcomes are not allowed in dedicated models")
    return result


def predictor_dictionary(dataset: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for block, predictors in PREDICTOR_BLOCKS.items():
        for predictor in predictors:
            if predictor not in dataset:
                raise KeyError(f"Dedicated predictor not found: {predictor}")
            rows.append(
                {
                    "block": block,
                    "predictor": predictor,
                    "n_nonmissing_full": int(to_numeric(dataset[predictor]).notna().sum()),
                    "components": "; ".join(COMPLETE_TOTALS.get(predictor, [])),
                }
            )
    for predictor in COMPLETE_TOTALS:
        rows.append(
            {
                "block": "totals_joint",
                "predictor": predictor,
                "n_nonmissing_full": int(to_numeric(dataset[predictor]).notna().sum()),
                "components": "; ".join(COMPLETE_TOTALS[predictor]),
            }
        )
    return pd.DataFrame(rows)


def pwm_ost_distribution_audit(dataset: pd.DataFrame) -> dict[str, pd.DataFrame]:
    samples = {
        "primary_n99": dataset.loc[dataset["included_primary_n99"]].copy(),
        "full_n101": dataset.copy(),
    }
    summary_rows = []
    frequency_rows = []
    high_case_rows = []
    for sample_scope, sample in samples.items():
        values = to_numeric(sample["PWM_OST_PRE"])
        observed = values.dropna()
        q1 = observed.quantile(0.25)
        q3 = observed.quantile(0.75)
        iqr = q3 - q1
        upper_fence = q3 + 1.5 * iqr
        paired = pd.DataFrame(
            {
                "pwm_ost": values,
                "pwm_trial": to_numeric(sample["PWM_TRIAL_PRE"]),
                "pwm_acc": to_numeric(sample["PWM_ACC_PRE"]),
            }
        )
        summary_rows.append(
            {
                "sample_scope": sample_scope,
                "sample_rows": len(sample),
                "n_observed": int(observed.notna().sum()),
                "n_missing": int(values.isna().sum()),
                "mean": observed.mean(),
                "sd": observed.std(ddof=1),
                "median": observed.median(),
                "q1": q1,
                "q3": q3,
                "minimum": observed.min(),
                "maximum": observed.max(),
                "skewness": observed.skew(),
                "excess_kurtosis": observed.kurt(),
                "unique_values": int(observed.nunique()),
                "iqr_upper_fence": upper_fence,
                "n_above_iqr_fence": int(observed.gt(upper_fence).sum()),
                "pearson_r_with_pwm_trial": paired.corr(method="pearson").loc["pwm_ost", "pwm_trial"],
                "spearman_rho_with_pwm_trial": paired.corr(method="spearman").loc["pwm_ost", "pwm_trial"],
                "pearson_r_with_pwm_acc": paired.corr(method="pearson").loc["pwm_ost", "pwm_acc"],
                "interpretive_note": "Discrete obstacle count; strongly related to number of PWM trials (exposure).",
            }
        )
        for value, count in observed.value_counts().sort_index().items():
            frequency_rows.append(
                {
                    "sample_scope": sample_scope,
                    "PWM_OST_PRE": value,
                    "count": int(count),
                    "percent_observed": float(count / len(observed) * 100),
                }
            )
        high = sample.loc[values.gt(upper_fence)].copy()
        for _, row in high.iterrows():
            high_case_rows.append(
                {
                    "sample_scope": sample_scope,
                    "ID": row["ID"],
                    "age": row["age"],
                    "Raven_ACC_PRE": row["Raven_ACC_PRE"],
                    "PWM_OST_PRE": row["PWM_OST_PRE"],
                    "PWM_ACC_PRE": row["PWM_ACC_PRE"],
                    "PWM_TRIAL_PRE": row["PWM_TRIAL_PRE"],
                    "PWM_EFF_PRE": row["PWM_EFF_PRE"],
                }
            )
    return {
        "summary": pd.DataFrame(summary_rows),
        "frequencies": pd.DataFrame(frequency_rows),
        "high_cases": pd.DataFrame(high_case_rows),
    }


def _zscore_complete(series: pd.Series) -> pd.Series:
    values = to_numeric(series)
    sd = values.std(ddof=1)
    if pd.isna(sd) or sd <= 0:
        return pd.Series(np.nan, index=series.index, dtype=float)
    return (values - values.mean()) / sd


def _vif_by_predictor(frame: pd.DataFrame, predictors: list[str], features: list[str]) -> dict[str, float]:
    if len(predictors) < 2:
        return {predictor: np.nan for predictor in predictors}
    design = sm.add_constant(frame[features], has_constant="add")
    result: dict[str, float] = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for predictor in predictors:
            position = list(design.columns).index(predictor)
            result[predictor] = float(variance_inflation_factor(design.to_numpy(), position))
    return result


def fit_model_pair(
    sample: pd.DataFrame,
    *,
    sample_scope: str,
    block: str,
    model_type: str,
    outcome: str,
    pre_col: str,
    outcome_family: str,
    predictors: list[str],
) -> list[dict]:
    # Raven is included in the complete-case definition for both models so
    # coefficient changes cannot be caused by a changing analytic sample.
    required = [pre_col, *predictors, "age", "Raven_ACC_PRE"]
    numeric = sample[required].apply(to_numeric).dropna()
    base = {
        "sample_scope": sample_scope,
        "block": block,
        "model_type": model_type,
        "outcome": outcome,
        "pre_col": pre_col,
        "outcome_family": outcome_family,
        "n": len(numeric),
    }
    if len(numeric) < cfg.MIN_N:
        return [
            {
                **base,
                "predictor": predictor,
                "covariate_spec": covariate_spec,
                "status": "insufficient_data",
            }
            for covariate_spec in ["without_raven", "with_raven"]
            for predictor in predictors
        ]

    standardized = pd.DataFrame(index=numeric.index)
    for column in required:
        standardized[column] = _zscore_complete(numeric[column])
    if standardized.isna().any().any():
        return [
            {
                **base,
                "predictor": predictor,
                "covariate_spec": covariate_spec,
                "status": "zero_variance",
            }
            for covariate_spec in ["without_raven", "with_raven"]
            for predictor in predictors
        ]

    rows = []
    for covariate_spec, include_raven in [
        ("without_raven", False),
        ("with_raven", True),
    ]:
        features = [*predictors, "age"]
        if include_raven:
            features.append("Raven_ACC_PRE")
        design = sm.add_constant(standardized[features], has_constant="add")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fit = sm.OLS(standardized[pre_col], design).fit(cov_type="HC3")
            vifs = _vif_by_predictor(standardized, predictors, features)
            for predictor in predictors:
                ci = fit.conf_int().loc[predictor]
                rows.append(
                    {
                        **base,
                        "predictor": predictor,
                        "covariate_spec": covariate_spec,
                        "status": "ok",
                        "beta_standardized": fit.params[predictor],
                        "se_hc3": fit.bse[predictor],
                        "ci_low": ci.iloc[0],
                        "ci_high": ci.iloc[1],
                        "p_value": fit.pvalues[predictor],
                        "r_squared": fit.rsquared,
                        "adj_r_squared": fit.rsquared_adj,
                        "vif": vifs[predictor],
                        "formula": "outcome_z ~ "
                        + " + ".join(f"{feature}_z" for feature in features),
                    }
                )
        except Exception as exc:
            for predictor in predictors:
                rows.append(
                    {
                        **base,
                        "predictor": predictor,
                        "covariate_spec": covariate_spec,
                        "status": f"{type(exc).__name__}: {exc}",
                    }
                )
    return rows


def _apply_block_fdr(models: pd.DataFrame) -> pd.DataFrame:
    result = models.copy()
    result["q_fdr_bh"] = np.nan
    ok = result["status"].eq("ok") & pd.to_numeric(result["p_value"], errors="coerce").notna()
    grouping = ["sample_scope", "block", "covariate_spec"]
    for _, index in result.loc[ok].groupby(grouping, sort=False).groups.items():
        corrected = fdr_bh(result.loc[index], "p_value")
        result.loc[index, "q_fdr_bh"] = corrected["q_fdr_bh"]
    result["significant_p05"] = pd.to_numeric(result["p_value"], errors="coerce") < cfg.ALPHA
    result["significant_fdr05"] = pd.to_numeric(result["q_fdr_bh"], errors="coerce") < cfg.ALPHA
    return result


def run_models(dataset: pd.DataFrame, outcomes: pd.DataFrame) -> pd.DataFrame:
    samples = {
        "primary_n99": dataset.loc[dataset["included_primary_n99"]].copy(),
        "sensitivity_n101": dataset.copy(),
    }
    rows: list[dict] = []
    for sample_scope, sample in samples.items():
        for _, outcome_row in outcomes.iterrows():
            common = {
                "sample": sample,
                "sample_scope": sample_scope,
                "outcome": outcome_row["outcome"],
                "pre_col": outcome_row["pre_col"],
                "outcome_family": outcome_row["outcome_family"],
            }
            for block, predictors in PREDICTOR_BLOCKS.items():
                for predictor in predictors:
                    rows.extend(
                        fit_model_pair(
                            **common,
                            block=block,
                            model_type="separate",
                            predictors=[predictor],
                        )
                    )
            rows.extend(
                fit_model_pair(
                    **common,
                    block="totals_joint",
                    model_type="joint",
                    predictors=list(COMPLETE_TOTALS),
                )
            )
    return _apply_block_fdr(pd.DataFrame(rows))


def compare_raven_models(models: pd.DataFrame) -> pd.DataFrame:
    ok = models.loc[models["status"].eq("ok")].copy()
    keys = [
        "sample_scope",
        "block",
        "model_type",
        "outcome",
        "pre_col",
        "outcome_family",
        "predictor",
    ]
    columns = keys + [
        "n",
        "beta_standardized",
        "se_hc3",
        "ci_low",
        "ci_high",
        "p_value",
        "q_fdr_bh",
        "r_squared",
        "adj_r_squared",
        "vif",
        "significant_fdr05",
    ]
    without = ok.loc[ok["covariate_spec"].eq("without_raven"), columns]
    with_raven = ok.loc[ok["covariate_spec"].eq("with_raven"), columns]
    comparison = without.merge(
        with_raven,
        on=keys,
        how="outer",
        validate="one_to_one",
        suffixes=("_without_raven", "_with_raven"),
    )
    unequal = comparison[
        comparison["n_without_raven"].ne(comparison["n_with_raven"])
    ]
    if not unequal.empty:
        raise RuntimeError("Paired Raven models do not use identical samples")
    comparison["beta_change_with_minus_without"] = (
        comparison["beta_standardized_with_raven"]
        - comparison["beta_standardized_without_raven"]
    )
    denominator = comparison["beta_standardized_without_raven"].abs()
    comparison["absolute_beta_attenuation_pct"] = np.where(
        denominator > 1e-12,
        (
            1
            - comparison["beta_standardized_with_raven"].abs()
            / denominator
        )
        * 100,
        np.nan,
    )
    comparison["adj_r_squared_change"] = (
        comparison["adj_r_squared_with_raven"]
        - comparison["adj_r_squared_without_raven"]
    )
    no_sig = comparison["significant_fdr05_without_raven"].fillna(False)
    raven_sig = comparison["significant_fdr05_with_raven"].fillna(False)
    comparison["significance_transition"] = np.select(
        [no_sig & raven_sig, no_sig & ~raven_sig, ~no_sig & raven_sig],
        ["significant_in_both", "lost_with_raven", "gained_with_raven"],
        default="not_significant_in_either",
    )
    return comparison.sort_values(
        ["sample_scope", "block", "q_fdr_bh_without_raven", "p_value_without_raven"],
        na_position="last",
    )


def build_block_summary(models: pd.DataFrame) -> pd.DataFrame:
    ok = models.loc[models["status"].eq("ok")].copy()
    return (
        ok.groupby(["sample_scope", "block", "covariate_spec"], dropna=False)
        .agg(
            models_ok=("p_value", "size"),
            significant_raw_p05=("significant_p05", "sum"),
            significant_fdr05=("significant_fdr05", "sum"),
            median_n=("n", "median"),
            min_n=("n", "min"),
            max_n=("n", "max"),
        )
        .reset_index()
    )


def _format_p(value: float) -> str:
    if pd.isna(value):
        return ""
    if value < 0.001:
        return "< .001"
    return f"{value:.3f}"


def paper_markdown(
    dataset: pd.DataFrame,
    models: pd.DataFrame,
    comparison: pd.DataFrame,
    block_summary: pd.DataFrame,
    pwm_ost_audit: dict[str, pd.DataFrame],
) -> str:
    primary = block_summary.loc[block_summary["sample_scope"].eq("primary_n99")]
    lines = [
        "## Dedicated ABAS-II/BRIEF-2 Total and Subscale Models",
        "",
        f"- Primary screened sample: {int(dataset['included_primary_n99'].sum())}",
        f"- Full-sample sensitivity: {len(dataset)}",
        f"- Raven screening flags: {int(dataset['raven_screen_flag'].sum())}",
        f"- User-selected non-Raven PRE outcomes: {len(CURATED_OUTCOMES)}",
        "- Outcomes: " + ", ".join(outcome for outcome, _, _ in CURATED_OUTCOMES) + ".",
        f"- Negative EFF values retained and flagged: PLANNING_EFF = {int(to_numeric(dataset['PLANNING_EFF_PRE']).lt(0).sum())}; PWM_EFF = {int(to_numeric(dataset['PWM_EFF_PRE']).lt(0).sum())}.",
        "- Each model was fitted on the same complete cases with and without Raven PRE accuracy.",
        "- Benjamini-Hochberg FDR was applied separately within each prespecified block.",
        "",
        "### Primary-Sample Result Counts",
        "",
        "| Block | Raven specification | Models | FDR-significant | Median n |",
        "|---|---|---:|---:|---:|",
    ]
    for _, row in primary.iterrows():
        lines.append(
            f"| {row['block']} | {row['covariate_spec']} | "
            f"{int(row['models_ok'])} | {int(row['significant_fdr05'])} | "
            f"{row['median_n']:.0f} |"
        )

    lines.extend(
        [
            "",
            "### Requested Raven-Adjusted Models",
            "",
            "| Sample | FDR-significant model terms |",
            "|---|---:|",
        ]
    )
    for sample_scope, label in [
        ("primary_n99", "Screened n=99 + Raven"),
        ("sensitivity_n101", "Full n=101 + Raven"),
    ]:
        subset = models.loc[
            models["sample_scope"].eq(sample_scope)
            & models["covariate_spec"].eq("with_raven")
            & models["significant_fdr05"].fillna(False)
        ]
        lines.append(f"| {label} | {len(subset)} |")

    pwm_summary = pwm_ost_audit["summary"].set_index("sample_scope")
    full_pwm = pwm_summary.loc["full_n101"]
    lines.extend(
        [
            "",
            "### Excluded PWM_OST Distribution Audit",
            "",
            f"- Observed values in the full sample: {int(full_pwm['n_observed'])}; missing: {int(full_pwm['n_missing'])}.",
            f"- Range: {full_pwm['minimum']:.0f}-{full_pwm['maximum']:.0f}; median: {full_pwm['median']:.0f}; skewness: {full_pwm['skewness']:.2f}.",
            f"- Cases above the 1.5-IQR upper fence: {int(full_pwm['n_above_iqr_fence'])}.",
            f"- Spearman correlation with PWM trial count: {full_pwm['spearman_rho_with_pwm_trial']:.2f}.",
            "- Interpretation: PWM_OST was excluded from the primary outcome set because it is a discrete, right-skewed obstacle count strongly related to task exposure.",
        ]
    )

    primary_comparison = comparison.loc[comparison["sample_scope"].eq("primary_n99")]
    significant = primary_comparison.loc[
        primary_comparison["significant_fdr05_without_raven"].fillna(False)
        | primary_comparison["significant_fdr05_with_raven"].fillna(False)
    ].copy()
    lines.extend(
        [
            "",
            "### FDR-Significant Primary-Sample Associations",
            "",
        ]
    )
    if significant.empty:
        lines.append("No dedicated primary-sample association survived FDR correction.")
    else:
        lines.extend(
            [
                "| Block | Predictor | Outcome | n | beta without Raven | q without Raven | beta with Raven | q with Raven | Transition |",
                "|---|---|---|---:|---:|---:|---:|---:|---|",
            ]
        )
        significant = significant.sort_values(
            ["q_fdr_bh_without_raven", "q_fdr_bh_with_raven"],
            na_position="last",
        )
        for _, row in significant.iterrows():
            lines.append(
                f"| {row['block']} | {row['predictor']} | {row['outcome']} | "
                f"{int(row['n_without_raven'])} | "
                f"{row['beta_standardized_without_raven']:.3f} | "
                f"{_format_p(row['q_fdr_bh_without_raven'])} | "
                f"{row['beta_standardized_with_raven']:.3f} | "
                f"{_format_p(row['q_fdr_bh_with_raven'])} | "
                f"{row['significance_transition']} |"
            )
    return "\n".join(lines) + "\n"


def run(dataset: pd.DataFrame) -> dict:
    prepared = add_complete_totals_and_screening(dataset)
    outcomes = outcome_dictionary(prepared)
    predictors = predictor_dictionary(prepared)
    models = run_models(prepared, outcomes)
    comparison = compare_raven_models(models)
    block_summary = build_block_summary(models)
    pwm_ost_audit = pwm_ost_distribution_audit(prepared)

    screening = prepared[
        [
            "ID",
            "age",
            "Raven_ACC_PRE",
            "raven_screen_cutoff",
            "raven_screen_flag",
            "raven_screen_status",
            "included_primary_n99",
            "ABAS_TOT_complete_components_observed",
            "BRIEF_TOT_complete_components_observed",
            "ABAS_TOT_complete",
            "BRIEF_TOT_complete",
        ]
    ].copy()
    manifest = pd.DataFrame(
        [
            {"item": "full_sample_n", "value": len(prepared)},
            {"item": "raven_screen_flagged", "value": int(prepared["raven_screen_flag"].sum())},
            {"item": "primary_sample_n", "value": int(prepared["included_primary_n99"].sum())},
            {"item": "curated_outcomes", "value": len(outcomes)},
            {"item": "selected_outcome_names", "value": "; ".join(outcomes["outcome"])},
            {"item": "planning_eff_negative_n", "value": int(to_numeric(prepared["PLANNING_EFF_PRE"]).lt(0).sum())},
            {"item": "pwm_eff_negative_n", "value": int(to_numeric(prepared["PWM_EFF_PRE"]).lt(0).sum())},
            {"item": "abas_standard_subscales", "value": len(ABAS_STANDARD_SCALES)},
            {"item": "brief_standard_subscales", "value": len(BRIEF_STANDARD_SCALES)},
            {"item": "brief_indices", "value": len(BRIEF_INDICES)},
            {"item": "primary_alpha", "value": cfg.ALPHA},
            {"item": "raven_role", "value": "screening and covariate only; never an outcome"},
        ]
    )

    workbook = OUT_DIR / "totals_subscales_models.xlsx"
    significant_primary = models.loc[
        models["sample_scope"].eq("primary_n99")
        & models["significant_fdr05"].fillna(False)
    ].copy()
    n99_with_raven = models.loc[
        models["sample_scope"].eq("primary_n99")
        & models["covariate_spec"].eq("with_raven")
    ].copy()
    n101_with_raven = models.loc[
        models["sample_scope"].eq("sensitivity_n101")
        & models["covariate_spec"].eq("with_raven")
    ].copy()
    write_workbook(
        workbook,
        {
            "manifest": manifest,
            "screening_audit": screening,
            "outcome_dictionary": outcomes,
            "predictor_dictionary": predictors,
            "model_results": models,
            "raven_comparison": comparison,
            "block_summary": block_summary,
            "significant_primary": significant_primary,
            "n99_with_raven": n99_with_raven,
            "n101_with_raven": n101_with_raven,
            "pwm_ost_distribution": pwm_ost_audit["summary"],
            "pwm_ost_frequencies": pwm_ost_audit["frequencies"],
            "pwm_ost_high_cases": pwm_ost_audit["high_cases"],
        },
    )

    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    comparison_csv = TABLE_DIR / "dedicated_totals_subscales_comparison.csv"
    significant_csv = TABLE_DIR / "dedicated_totals_subscales_significant.csv"
    n99_raven_csv = TABLE_DIR / "dedicated_n99_with_raven_results.csv"
    n101_raven_csv = TABLE_DIR / "dedicated_n101_with_raven_results.csv"
    pwm_ost_csv = TABLE_DIR / "pwm_ost_distribution_audit.csv"
    summary_md = TABLE_DIR / "dedicated_totals_subscales_summary.md"
    comparison.to_csv(comparison_csv, index=False, encoding="utf-8-sig")
    significant_primary.to_csv(significant_csv, index=False, encoding="utf-8-sig")
    n99_with_raven.to_csv(n99_raven_csv, index=False, encoding="utf-8-sig")
    n101_with_raven.to_csv(n101_raven_csv, index=False, encoding="utf-8-sig")
    pwm_ost_audit["summary"].to_csv(pwm_ost_csv, index=False, encoding="utf-8-sig")
    markdown = paper_markdown(
        prepared,
        models,
        comparison,
        block_summary,
        pwm_ost_audit,
    )
    summary_md.write_text(markdown, encoding="utf-8")
    return {
        "prepared": prepared,
        "outcomes": outcomes,
        "predictors": predictors,
        "models": models,
        "comparison": comparison,
        "block_summary": block_summary,
        "pwm_ost_audit": pwm_ost_audit,
        "paper_markdown": markdown,
        "files": [
            workbook,
            comparison_csv,
            significant_csv,
            n99_raven_csv,
            n101_raven_csv,
            pwm_ost_csv,
            summary_md,
        ],
    }
