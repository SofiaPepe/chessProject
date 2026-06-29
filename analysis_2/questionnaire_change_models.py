from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from common import fdr_bh, to_numeric, write_workbook
from config import ALPHA, GROUP_COLUMN, OUTPUT_ROOT


OUT_DIR = OUTPUT_ROOT / "08_questionnaire_change_models"
MIN_N = 25


def zscore(series: pd.Series) -> pd.Series:
    values = to_numeric(series)
    sd = values.std(ddof=1)
    return (values - values.mean()) / sd if pd.notna(sd) and sd > 0 else pd.Series(np.nan, index=series.index)


def selected_questionnaire_pairs(predictor_main: pd.DataFrame) -> pd.DataFrame:
    if predictor_main.empty:
        return pd.DataFrame(columns=["predictor", "outcome", "source_p_value", "source_q_fdr_bh"])
    mask = (
        predictor_main["status"].eq("ok")
        & predictor_main["predictor"].astype(str).str.startswith(("ABAS_", "BRIEF_"))
        & predictor_main["significant_p05"].fillna(False).astype(bool)
    )
    columns = ["predictor", "outcome", "p_value", "q_fdr_bh"]
    pairs = predictor_main.loc[mask, columns].copy()
    pairs = pairs.rename(columns={"p_value": "source_p_value", "q_fdr_bh": "source_q_fdr_bh"})
    return pairs.sort_values(["source_p_value", "predictor", "outcome"]).reset_index(drop=True)


def fit_change_model(df: pd.DataFrame, outcome: str, predictor: str) -> dict:
    pre_col = f"{outcome}_PRE"
    post_col = f"{outcome}_POST"
    base = {"predictor": predictor, "outcome": outcome, "pre_col": pre_col, "post_col": post_col}
    if pre_col not in df or post_col not in df or predictor not in df:
        return {**base, "n": 0, "status": "missing_column"}

    data = pd.DataFrame(
        {
            "post": to_numeric(df[post_col]),
            "pre": to_numeric(df[pre_col]),
            "group_experimental": (to_numeric(df[GROUP_COLUMN]) == 1).astype(float),
            "age_z": zscore(df["age"]),
            "predictor_z": zscore(df[predictor]),
        }
    ).dropna()
    base["n"] = len(data)
    if len(data) < MIN_N or data["group_experimental"].nunique() < 2:
        return {**base, "status": "insufficient_data"}

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = smf.ols("post ~ pre + group_experimental + age_z + predictor_z", data=data).fit(cov_type="HC3")
        group_ci = fit.conf_int().loc["group_experimental"]
        predictor_ci = fit.conf_int().loc["predictor_z"]
        return {
            **base,
            "status": "ok",
            "formula": "post ~ pre + group_experimental + age_z + predictor_z",
            "group_beta": fit.params["group_experimental"],
            "group_se": fit.bse["group_experimental"],
            "group_ci_low": group_ci.iloc[0],
            "group_ci_high": group_ci.iloc[1],
            "group_p": fit.pvalues["group_experimental"],
            "predictor_beta": fit.params["predictor_z"],
            "predictor_se": fit.bse["predictor_z"],
            "predictor_ci_low": predictor_ci.iloc[0],
            "predictor_ci_high": predictor_ci.iloc[1],
            "predictor_p": fit.pvalues["predictor_z"],
            "r_squared": fit.rsquared,
            "adj_r_squared": fit.rsquared_adj,
        }
    except Exception as exc:
        return {**base, "status": f"{type(exc).__name__}: {exc}"}


def run(df: pd.DataFrame, predictor_main: pd.DataFrame) -> dict:
    pairs = selected_questionnaire_pairs(predictor_main)
    rows = [fit_change_model(df, row["outcome"], row["predictor"]) for _, row in pairs.iterrows()]
    models = pd.DataFrame(rows)
    if not models.empty:
        source_lookup = pairs.set_index(["predictor", "outcome"])
        models["source_p_value"] = [
            source_lookup.loc[(row["predictor"], row["outcome"]), "source_p_value"]
            if (row["predictor"], row["outcome"]) in source_lookup.index
            else np.nan
            for _, row in models.iterrows()
        ]
        models["source_q_fdr_bh"] = [
            source_lookup.loc[(row["predictor"], row["outcome"]), "source_q_fdr_bh"]
            if (row["predictor"], row["outcome"]) in source_lookup.index
            else np.nan
            for _, row in models.iterrows()
        ]
        models = fdr_bh(models, "group_p", "group_q_fdr_bh")
        models = fdr_bh(models, "predictor_p", "predictor_q_fdr_bh")
        models["group_significant_p05"] = models["group_p"] < ALPHA
        models["group_significant_fdr05"] = models["group_q_fdr_bh"] < ALPHA
        models["predictor_significant_p05"] = models["predictor_p"] < ALPHA
        models["predictor_significant_fdr05"] = models["predictor_q_fdr_bh"] < ALPHA

    path = OUT_DIR / "questionnaire_change_models.xlsx"
    write_workbook(
        path,
        {
            "selected_pairs": pairs,
            "ancova_models": models,
            "significant_predictors": models[models.get("predictor_significant_p05", False) == True] if not models.empty else models,
            "significant_group_effects": models[models.get("group_significant_p05", False) == True] if not models.empty else models,
        },
    )
    return {"pairs": pairs, "models": models, "files": [path]}
