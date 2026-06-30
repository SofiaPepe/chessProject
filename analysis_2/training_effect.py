from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

from common import (
    cohen_dz,
    fdr_bh,
    find_prepost_pairs,
    hedges_g,
    normality_safe_wilcoxon,
    numeric_summary,
    plot_prepost,
    safe_filename,
    to_numeric,
    write_workbook,
)
from config import ALPHA, GROUP_COLUMN, GROUP_LABELS, ID_COLUMN, OUTPUT_ROOT


OUT_DIR = OUTPUT_ROOT / "04_training_effect"
PLOT_DIR = OUT_DIR / "plots"


def group_time_model(data: pd.DataFrame, pair: dict) -> dict:
    long = pd.concat(
        [
            data[[ID_COLUMN, GROUP_COLUMN, "age"]].assign(
                score=data["pre"],
                time_post=0.0,
            ),
            data[[ID_COLUMN, GROUP_COLUMN, "age"]].assign(
                score=data["post"],
                time_post=1.0,
            ),
        ],
        ignore_index=True,
    )
    long["group_experimental"] = (
        to_numeric(long[GROUP_COLUMN]) == 1
    ).astype(float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = smf.ols(
            "score ~ time_post * group_experimental + age",
            data=long,
        ).fit(
            cov_type="cluster",
            cov_kwds={"groups": long[ID_COLUMN]},
        )
    term = "time_post:group_experimental"
    beta = fit.params[term]
    se = fit.bse[term]
    t_value = beta / se if se else np.nan
    partial_eta_squared = (t_value ** 2) / (t_value ** 2 + fit.df_resid) if pd.notna(t_value) else np.nan
    ci = fit.conf_int().loc[term]
    return {
        "variable": pair["variable"],
        "term": term,
        "model": "score ~ time * group + age; participant-clustered SE",
        "beta_difference_in_change": beta,
        "se_clustered_by_participant": se,
        "ci_low": ci.iloc[0],
        "ci_high": ci.iloc[1],
        "p_value": fit.pvalues[term],
        "partial_eta_squared": partial_eta_squared,
        "r_squared": fit.rsquared,
    }


def run(df: pd.DataFrame) -> dict:
    pairs = find_prepost_pairs(df)
    group_time_models = []
    interactions = []
    within_rows = []
    change_rows = []
    descriptive_rows = []
    skipped = []

    for pair in pairs:
        data = df[
            [ID_COLUMN, GROUP_COLUMN, "age", pair["pre_col"], pair["post_col"]]
        ].copy()
        data["pre"] = to_numeric(data[pair["pre_col"]])
        data["post"] = to_numeric(data[pair["post_col"]])
        data["age"] = to_numeric(data["age"])
        data = data.dropna(subset=[ID_COLUMN, GROUP_COLUMN, "age", "pre", "post"])
        if len(data) < 6 or data[GROUP_COLUMN].nunique() < 2:
            skipped.append({**pair, "reason": "insufficient_complete_pairs_or_groups", "n": len(data)})
            continue
        if data[["pre", "post"]].stack().nunique() < 2:
            skipped.append({**pair, "reason": "zero_variance", "n": len(data)})
            continue

        data["change"] = data["post"] - data["pre"]
        try:
            model_row = group_time_model(data, pair)
            group_time_models.append({**pair, **model_row})
            interaction_p = model_row["p_value"]
            interaction_np2 = model_row["partial_eta_squared"]
            interactions.append(
                {
                    **pair,
                    "n_ids": data[ID_COLUMN].nunique(),
                    "n_experimental": int((data[GROUP_COLUMN] == 1).sum()),
                    "n_control": int((data[GROUP_COLUMN] == 2).sum()),
                    "interaction_p": interaction_p,
                    "interaction_np2": interaction_np2,
                }
            )
        except Exception as exc:
            skipped.append({**pair, "reason": f"group_time_model_{type(exc).__name__}: {exc}", "n": len(data)})
            interaction_p = np.nan

        for code, label in GROUP_LABELS.items():
            group = data[data[GROUP_COLUMN] == code]
            if group.empty:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                paired_p = stats.ttest_rel(group["post"], group["pre"]).pvalue if len(group) >= 2 else np.nan
            within_rows.append(
                {
                    "variable": pair["variable"],
                    "group": label,
                    "n": len(group),
                    "pre_mean": group["pre"].mean(),
                    "pre_sd": group["pre"].std(ddof=1),
                    "post_mean": group["post"].mean(),
                    "post_sd": group["post"].std(ddof=1),
                    "mean_change": group["change"].mean(),
                    "paired_t_p": paired_p,
                    "wilcoxon_p": normality_safe_wilcoxon(group["pre"], group["post"]),
                    "cohen_dz": cohen_dz(group["change"]),
                }
            )
            for occasion, column in [("PRE", "pre"), ("POST", "post")]:
                descriptive_rows.append({"variable": pair["variable"], "group": label, "time": occasion, **numeric_summary(group[column])})

        experimental = data.loc[data[GROUP_COLUMN] == 1, "change"]
        control = data.loc[data[GROUP_COLUMN] == 2, "change"]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            welch_p = stats.ttest_ind(experimental, control, equal_var=False).pvalue if len(experimental) >= 2 and len(control) >= 2 else np.nan
            try:
                mann_p = stats.mannwhitneyu(experimental, control, alternative="two-sided").pvalue
            except ValueError:
                mann_p = np.nan
        change_rows.append(
            {
                "variable": pair["variable"],
                "n_experimental": len(experimental),
                "n_control": len(control),
                "experimental_mean_change": experimental.mean(),
                "control_mean_change": control.mean(),
                "difference_in_change": experimental.mean() - control.mean(),
                "hedges_g_change": hedges_g(experimental, control),
                "welch_p": welch_p,
                "mann_whitney_p": mann_p,
            }
        )

    interaction_df = fdr_bh(pd.DataFrame(interactions), "interaction_p")
    if not interaction_df.empty:
        interaction_df["significant_p05"] = interaction_df["interaction_p"] < ALPHA
        interaction_df["significant_fdr05"] = interaction_df["q_fdr_bh"] < ALPHA
        interaction_df = interaction_df.sort_values(["significant_fdr05", "interaction_p"], ascending=[False, True])
    within_df = fdr_bh(pd.DataFrame(within_rows), "paired_t_p")
    change_df = fdr_bh(pd.DataFrame(change_rows), "welch_p")

    plot_rows = []
    p_lookup = dict(zip(interaction_df.get("variable", []), interaction_df.get("interaction_p", [])))
    for pair in pairs:
        plot_path = PLOT_DIR / f"{safe_filename(pair['variable'])}_prepost_by_group.png"
        made = plot_prepost(df, pair, plot_path, p_lookup.get(pair["variable"], np.nan))
        plot_rows.append({"variable": pair["variable"], "path": str(plot_path), "created": made})

    path = OUT_DIR / "training_effect_results.xlsx"
    write_workbook(
        path,
        {
            "group_x_time": interaction_df,
            "group_x_time_model": pd.DataFrame(group_time_models),
            "within_group": within_df,
            "change_comparison": change_df,
            "descriptives": pd.DataFrame(descriptive_rows),
            "skipped": pd.DataFrame(skipped),
            "plot_manifest": pd.DataFrame(plot_rows),
        },
    )
    return {
        "interactions": interaction_df,
        "covariate": interaction_df,
        "within": within_df,
        "change": change_df,
        "skipped": pd.DataFrame(skipped),
        "files": [path, *[Path(row["path"]) for row in plot_rows if row["created"]]],
    }
