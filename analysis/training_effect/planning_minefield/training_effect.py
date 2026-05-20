from pathlib import Path
import sys
import warnings

import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.formula.api as smf

sys.path.append(str(Path(__file__).resolve().parents[1] / "shared"))

from training_effect_common import (  # noqa: E402
    ALPHA,
    GROUP_LABELS,
    ID_COL,
    TRAINING_OUTPUT,
    add_fdr,
    create_long_format,
    find_prepost_pairs,
    load_analysis_dataset,
    normalize_name,
    plot_prepost_by_group,
    safe_filename,
    to_numeric,
    write_excel_with_highlights,
)


OUT_DIR = TRAINING_OUTPUT / "planning_minefield"
RESULTS_XLSX = OUT_DIR / "planning_minefield_training_effect_results.xlsx"
PLOTS_ALL_DIR = OUT_DIR / "prepost_plots_all_variables"

GROUP_TIME_FORMULA = "value ~ time_post * group_experimental"
INTERACTION_TERM = "time_post:group_experimental"

OUTCOME_DEFS = {
    "planning_diff_pre": {
        "variable": "Planning",
        "time": "PRE",
        "matt": "PLANNING_MATT_PRE",
        "min": "PLANNING_MATTI_MIN_PRE",
    },
    "planning_diff_post": {
        "variable": "Planning",
        "time": "POST",
        "matt": "PLANNING_MATT_POST",
        "min": "PLANNING_MATTI_MIN_POST",
    },
    "pwm_diff_pre": {
        "variable": "PWM",
        "time": "PRE",
        "matt": "PWM_MATT_PRE",
        "min": "PWM_MATT_MIN_PRE",
    },
    "pwm_diff_post": {
        "variable": "PWM",
        "time": "POST",
        "matt": "PWM_MATT_POST",
        "min": "PWM_MATT_MIN_POST",
    },
}

DERIVED_PAIRS = [
    {"variable": "Planning", "pre_col": "planning_diff_pre", "post_col": "planning_diff_post"},
    {"variable": "PWM", "pre_col": "pwm_diff_pre", "post_col": "pwm_diff_post"},
]


def find_col(df: pd.DataFrame, target: str) -> str:
    lookup = {normalize_name(col): col for col in df.columns}
    col = lookup.get(normalize_name(target))
    if col is None:
        raise KeyError(f"Column not found: {target}")
    return col


def add_outcomes(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    invalid_rows = []
    checks = []

    for outcome, spec in OUTCOME_DEFS.items():
        matt_col = find_col(df, spec["matt"])
        min_col = find_col(df, spec["min"])
        matt = to_numeric(df[matt_col])
        min_tiles = to_numeric(df[min_col])
        raw = matt - min_tiles

        invalid_negative = raw < 0
        invalid_high = raw > 50
        invalid = invalid_negative | invalid_high

        df[f"{outcome}_raw"] = raw
        df[f"{outcome}_excluded"] = invalid.fillna(False)
        df[f"{outcome}_excluded_reason"] = np.select(
            [invalid_negative.fillna(False), invalid_high.fillna(False)],
            ["negative", "above_50"],
            default="",
        )
        df[outcome] = raw.where(~invalid)

        for idx in df.index[invalid.fillna(False)]:
            invalid_rows.append(
                {
                    "ID": df.loc[idx, "ID"],
                    "group": df.loc[idx, "group"],
                    "group_label": df.loc[idx, "group_label"],
                    "sex": df.loc[idx, "sex"] if "sex" in df.columns else np.nan,
                    "age": df.loc[idx, "age"] if "age" in df.columns else np.nan,
                    "class": df.loc[idx, "class"] if "class" in df.columns else np.nan,
                    "variable": spec["variable"],
                    "time": spec["time"],
                    "outcome": outcome,
                    "raw_diff": raw.loc[idx],
                    "reason": df.loc[idx, f"{outcome}_excluded_reason"],
                    "matt_col": matt_col,
                    "matt_value": matt.loc[idx],
                    "min_col": min_col,
                    "min_value": min_tiles.loc[idx],
                }
            )

        checks.append(
            {
                "outcome": outcome,
                "variable": spec["variable"],
                "time": spec["time"],
                "raw_n": int(raw.notna().sum()),
                "valid_n": int(df[outcome].notna().sum()),
                "negative_n": int(invalid_negative.sum()),
                "above_50_n": int(invalid_high.sum()),
                "missing_after_cleaning": int(df[outcome].isna().sum()),
                "raw_min": raw.min(),
                "raw_max": raw.max(),
            }
        )

    return pd.DataFrame(invalid_rows), pd.DataFrame(checks)


def summarize_numeric(values: pd.Series) -> dict[str, float]:
    values = to_numeric(values).dropna()
    if values.empty:
        return {
            "n": 0,
            "mean": np.nan,
            "sd": np.nan,
            "median": np.nan,
            "q1": np.nan,
            "q3": np.nan,
            "min": np.nan,
            "max": np.nan,
        }
    return {
        "n": int(values.count()),
        "mean": values.mean(),
        "sd": values.std(ddof=1),
        "median": values.median(),
        "q1": values.quantile(0.25),
        "q3": values.quantile(0.75),
        "min": values.min(),
        "max": values.max(),
    }


def build_descriptives(df: pd.DataFrame, checks: pd.DataFrame) -> pd.DataFrame:
    rows = [{"section": "sample", "variable": "N_total", "level": "all", "n": len(df)}]

    for variable in ["group_label", "sex", "age", "class", "section"]:
        if variable not in df.columns:
            continue
        for level, n in df[variable].value_counts(dropna=False).sort_index().items():
            rows.append(
                {
                    "section": "sample_counts",
                    "variable": variable,
                    "level": level,
                    "n": int(n),
                }
            )

    for group_label in ["all", *GROUP_LABELS.values()]:
        subset = df if group_label == "all" else df[df["group_label"] == group_label]
        for pair in DERIVED_PAIRS:
            for time, col in [("PRE", pair["pre_col"]), ("POST", pair["post_col"])]:
                check = checks.loc[checks["outcome"] == col].iloc[0]
                rows.append(
                    {
                        "section": "outcome_descriptives",
                        "variable": pair["variable"],
                        "time": time,
                        "group": group_label,
                        "outcome": col,
                        "missing": int(subset[col].isna().sum()),
                        "excluded_invalid": int(subset[f"{col}_excluded"].sum()),
                        "raw_n_total": int(check["raw_n"]) if group_label == "all" else np.nan,
                        **summarize_numeric(subset[col]),
                    }
                )

    return pd.DataFrame(rows)


def paired_test(df: pd.DataFrame, pre_col: str, post_col: str, variable: str, group_label: str = "all") -> dict:
    subset = pd.DataFrame(
        {
            pre_col: to_numeric(df[pre_col]),
            post_col: to_numeric(df[post_col]),
        }
    ).dropna()

    if len(subset) < 3:
        return {
            "variable": variable,
            "pre_col": pre_col,
            "post_col": post_col,
            "group": group_label,
            "n_pairs": len(subset),
            "status": "skipped_insufficient_pairs",
        }

    pre = subset[pre_col]
    post = subset[post_col]
    diff = post - pre
    t_stat, t_p = stats.ttest_rel(post, pre, nan_policy="omit")
    try:
        w_stat, w_p = stats.wilcoxon(post, pre, zero_method="wilcox")
    except ValueError:
        w_stat, w_p = np.nan, np.nan

    diff_sd = diff.std(ddof=1)
    return {
        "variable": variable,
        "pre_col": pre_col,
        "post_col": post_col,
        "group": group_label,
        "status": "ok",
        "n_pairs": int(len(subset)),
        "pre_mean": pre.mean(),
        "pre_sd": pre.std(ddof=1),
        "post_mean": post.mean(),
        "post_sd": post.std(ddof=1),
        "change_mean_post_minus_pre": diff.mean(),
        "change_sd": diff_sd,
        "cohen_dz": diff.mean() / diff_sd if pd.notna(diff_sd) and diff_sd != 0 else np.nan,
        "paired_t": t_stat,
        "paired_t_df": int(len(subset) - 1),
        "paired_t_p": t_p,
        "paired_t_significant_p05": bool(t_p < ALPHA) if pd.notna(t_p) else np.nan,
        "wilcoxon_w": w_stat,
        "wilcoxon_p": w_p,
        "wilcoxon_significant_p05": bool(w_p < ALPHA) if pd.notna(w_p) else np.nan,
    }


def run_prepost_ttests(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for pair in DERIVED_PAIRS:
        for group_label, subset in [
            ("all", df),
            ("experimental", df[df["group_label"] == "experimental"]),
            ("control", df[df["group_label"] == "control"]),
        ]:
            rows.append(paired_test(subset, pair["pre_col"], pair["post_col"], pair["variable"], group_label))

    results = pd.DataFrame(rows)
    if "paired_t_p" in results.columns:
        results = add_fdr(results, "paired_t_p", "paired_t_q_fdr_bh")
        results["paired_t_significant_fdr05"] = results["paired_t_q_fdr_bh"] < ALPHA
    return results


def run_all_prepost_ttests(df: pd.DataFrame, prepost_pairs: list[dict[str, str]]) -> pd.DataFrame:
    rows = []
    for pair in prepost_pairs:
        for group_label, subset in [
            ("all", df),
            ("experimental", df[df["group_label"] == "experimental"]),
            ("control", df[df["group_label"] == "control"]),
        ]:
            rows.append(paired_test(subset, pair["pre_col"], pair["post_col"], pair["variable"], group_label))

    results = pd.DataFrame(rows)
    if "paired_t_p" in results.columns:
        results = add_fdr(results, "paired_t_p", "paired_t_q_fdr_bh")
        results["paired_t_significant_fdr05"] = results["paired_t_q_fdr_bh"] < ALPHA
    return results


def fit_group_time_model(df: pd.DataFrame, pair: dict[str, str]) -> list[dict]:
    long_df = create_long_format(df, pair, paired_only=True)
    long_df = long_df.dropna(subset=["value", "time_post", "group_experimental"])
    if long_df.empty or long_df["group_experimental"].nunique() < 2 or long_df[ID_COL].nunique() < 5:
        return [
            {
                **pair,
                "analysis": "group_x_time_model",
                "status": "skipped_insufficient_complete_pairs_or_groups",
                "n_obs": int(long_df.shape[0]),
                "n_ids": int(long_df[ID_COL].nunique()) if not long_df.empty else 0,
            }
        ]

    last_error = None
    fit = None
    model_type = None
    method_used = None
    for method in ["lbfgs", "powell", "cg", "bfgs", "nm"]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = smf.mixedlm(GROUP_TIME_FORMULA, long_df, groups=long_df[ID_COL])
                fit = model.fit(reml=False, method=method, maxiter=2000, disp=False)
            if not getattr(fit, "converged", True):
                raise RuntimeError(f"MixedLM did not converge with {method}")
            model_type = "mixedlm_random_intercept"
            method_used = method
            break
        except Exception as exc:
            fit = None
            last_error = exc

    if fit is None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = smf.ols(GROUP_TIME_FORMULA, long_df).fit(
                cov_type="cluster",
                cov_kwds={"groups": long_df[ID_COL]},
            )
        model_type = f"ols_clustered_by_ID_fallback_after_{type(last_error).__name__}"
        method_used = "clustered_ols"
        params = fit.params
        bse = fit.bse
        pvalues = fit.pvalues
        conf = fit.conf_int()
    else:
        params = fit.fe_params
        bse = fit.bse.reindex(params.index)
        pvalues = fit.pvalues.reindex(params.index)
        conf = fit.conf_int().reindex(params.index)

    rows = []
    for term in params.index:
        se = bse.loc[term]
        rows.append(
            {
                **pair,
                "analysis": "group_x_time_model",
                "status": "ok",
                "model_type": model_type,
                "fit_method": method_used,
                "term": term,
                "effect": "group_x_time" if term == INTERACTION_TERM else term,
                "estimate": params.loc[term],
                "se": se,
                "z_or_t": params.loc[term] / se if pd.notna(se) and se != 0 else np.nan,
                "p_value": pvalues.loc[term],
                "ci_low": conf.loc[term, 0],
                "ci_high": conf.loc[term, 1],
                "n_obs": int(long_df.shape[0]),
                "n_ids": int(long_df[ID_COL].nunique()),
            }
        )
    return rows


def run_prepost_with_group(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for pair in DERIVED_PAIRS:
        rows.extend(fit_group_time_model(df, pair))
        for group_label in ["experimental", "control"]:
            group_df = df[df["group_label"] == group_label]
            result = paired_test(group_df, pair["pre_col"], pair["post_col"], pair["variable"], group_label)
            result["analysis"] = "paired_within_group"
            result["significant_p05"] = result.get("paired_t_significant_p05", np.nan)
            rows.append(result)
    return pd.DataFrame(rows)


def run_prepost_without_group(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for pair in DERIVED_PAIRS:
        result = paired_test(df, pair["pre_col"], pair["post_col"], pair["variable"])
        result["significant_p05"] = result.get("paired_t_significant_p05", np.nan)
        rows.append(result)
    return pd.DataFrame(rows)


def make_all_prepost_plots(df: pd.DataFrame, prepost_pairs: list[dict[str, str]]) -> pd.DataFrame:
    PLOTS_ALL_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    for pair in prepost_pairs:
        try:
            long_df = create_long_format(df, pair, paired_only=False)
            path = PLOTS_ALL_DIR / f"{safe_filename(pair['variable'])}_prepost_by_group.png"
            plot_prepost_by_group(
                long_df,
                pair["variable"],
                path,
                title=f"{pair['variable']}: PRE vs POST by group",
            )
            manifest.append({**pair, "plot_path": str(path), "status": "created"})
        except Exception as exc:
            manifest.append({**pair, "plot_path": "", "status": f"error: {type(exc).__name__}: {exc}"})
    return pd.DataFrame(manifest)


def make_specific_plots(df: pd.DataFrame, prepost_with_group: pd.DataFrame) -> None:
    p_lookup = {}
    model_rows = prepost_with_group[
        (prepost_with_group.get("analysis") == "group_x_time_model")
        & (prepost_with_group.get("effect") == "group_x_time")
    ]
    for _, row in model_rows.iterrows():
        p_lookup[row["variable"]] = row.get("p_value", np.nan)

    for pair in DERIVED_PAIRS:
        long_df = create_long_format(df, pair, paired_only=False)
        plot_prepost_by_group(
            long_df,
            pair["variable"],
            OUT_DIR / f"{safe_filename(pair['variable'])}_diff_prepost_by_group.png",
            p_value=p_lookup.get(pair["variable"]),
            title=f"{pair['variable']}: tiles traveled minus minimum tiles",
            ylabel="Tile difference",
        )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_analysis_dataset()

    invalid_values, checks = add_outcomes(df)
    prepost_pairs = find_prepost_pairs(df)
    descriptives = build_descriptives(df, checks)
    ttests_pre_post = run_prepost_ttests(df)
    all_prepost_ttests = run_all_prepost_ttests(df, prepost_pairs)
    all_prepost_plots = make_all_prepost_plots(df, prepost_pairs)
    prepost_without_group = run_prepost_without_group(df)
    prepost_with_group = run_prepost_with_group(df)

    if "p_value" in prepost_with_group.columns:
        model_mask = prepost_with_group["analysis"].eq("group_x_time_model") & prepost_with_group["p_value"].notna()
        prepost_with_group.loc[model_mask, "significant_p05"] = prepost_with_group.loc[model_mask, "p_value"] < ALPHA

    write_excel_with_highlights(
        RESULTS_XLSX,
        {
            "descriptives": descriptives,
            "excluded_values": invalid_values,
            "t_test_pre_post": ttests_pre_post,
            "t_test_pre_post_all": all_prepost_ttests,
            "all_variable_plots": all_prepost_plots,
            "prepost_without_group": prepost_without_group,
            "prepost_with_group": prepost_with_group,
        },
    )
    make_specific_plots(df, prepost_with_group)

    complete_planning = df[["planning_diff_pre", "planning_diff_post"]].dropna().shape[0]
    complete_pwm = df[["pwm_diff_pre", "pwm_diff_post"]].dropna().shape[0]
    print("Planning Minefield training-effect analysis complete")
    print(f"Input N: {len(df)}")
    print(f"Complete pairs Planning: {complete_planning}")
    print(f"Complete pairs PWM: {complete_pwm}")
    print(f"Results workbook: {RESULTS_XLSX}")


if __name__ == "__main__":
    main()
