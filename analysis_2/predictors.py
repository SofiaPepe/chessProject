from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from common import fdr_bh, find_prepost_pairs, to_numeric, write_workbook
from config import ALPHA, GROUP_COLUMN, ID_COLUMN, OUTPUT_ROOT


OUT_DIR = OUTPUT_ROOT / "06_predictors"
MIN_N = 25


def candidate_predictors(df: pd.DataFrame) -> pd.DataFrame:
    pre_columns = {pair["pre_col"] for pair in find_prepost_pairs(df) if pair["transformation"] == "raw"}
    questionnaire = {column for column in df.columns if str(column).startswith(("ABAS_", "BRIEF_"))}
    rows = []
    for column in sorted(pre_columns | questionnaire):
        values = to_numeric(df[column])
        if values.notna().sum() < MIN_N or values.nunique(dropna=True) < 2:
            continue
        rows.append(
            {
                "predictor": column,
                "type": "questionnaire" if column in questionnaire else "baseline_pre",
                "n": int(values.notna().sum()),
                "mean": values.mean(),
                "sd": values.std(ddof=1),
            }
        )
    return pd.DataFrame(rows)


def questionnaire_predictors(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in sorted(
        column for column in df.columns if str(column).startswith(("ABAS_", "BRIEF_"))
    ):
        values = to_numeric(df[column])
        if values.notna().sum() < MIN_N or values.nunique(dropna=True) < 2:
            continue
        rows.append(
            {
                "predictor": column,
                "type": "questionnaire",
                "n": int(values.notna().sum()),
                "mean": values.mean(),
                "sd": values.std(ddof=1),
            }
        )
    return pd.DataFrame(rows)


def zscore(series: pd.Series) -> pd.Series:
    values = to_numeric(series)
    sd = values.std(ddof=1)
    return (values - values.mean()) / sd if pd.notna(sd) and sd > 0 else pd.Series(np.nan, index=series.index)


def fit_model(data: pd.DataFrame, interaction: bool, questionnaire: bool) -> dict:
    if questionnaire:
        terms = ["predictor_z", "age_z"]
        if interaction:
            terms = ["predictor_z", "predictor_z:group_experimental", "group_experimental", "age_z"]
    else:
        terms = ["predictor_z", "group_experimental", "age_z"]
        if interaction:
            terms.insert(1, "predictor_z:group_experimental")
        if data["sex"].nunique() > 1:
            terms.append("C(sex)")
        if data["class_cov"].nunique() > 1:
            terms.append("C(class_cov)")
    formula = "effectiveness_pct ~ " + " + ".join(terms)
    term = "predictor_z:group_experimental" if interaction else "predictor_z"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = smf.ols(formula, data=data).fit(cov_type="HC3")
    ci = fit.conf_int().loc[term]
    return {
        "term": term,
        "beta": fit.params[term],
        "se": fit.bse[term],
        "ci_low": ci.iloc[0],
        "ci_high": ci.iloc[1],
        "p_value": fit.pvalues[term],
        "r_squared": fit.rsquared,
        "adj_r_squared": fit.rsquared_adj,
        "formula": formula,
    }


def pre_questionnaire_models(df: pd.DataFrame) -> pd.DataFrame:
    predictors = questionnaire_predictors(df)
    pairs = find_prepost_pairs(df)
    rows = []
    for predictor in predictors["predictor"].tolist():
        for pair in pairs:
            data = df[[predictor, pair["pre_col"], "age"]].copy()
            data["predictor_z"] = zscore(data[predictor])
            data["outcome_z"] = zscore(data[pair["pre_col"]])
            data["age_z"] = zscore(data["age"])
            data = data.dropna(subset=["predictor_z", "outcome_z", "age_z"])
            base = {
                "predictor": predictor,
                "outcome": pair["variable"],
                "pre_col": pair["pre_col"],
                "domain": pair["domain"],
                "transformation": pair["transformation"],
                "n": len(data),
                "model": "PRE outcome_z ~ questionnaire predictor_z + age_z",
            }
            if len(data) < MIN_N:
                rows.append({**base, "status": "insufficient_data"})
                continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    fit = smf.ols(
                        "outcome_z ~ predictor_z + age_z",
                        data=data,
                    ).fit(cov_type="HC3")
                ci = fit.conf_int().loc["predictor_z"]
                rows.append(
                    {
                        **base,
                        "status": "ok",
                        "term": "predictor_z",
                        "beta_standardized": fit.params["predictor_z"],
                        "se_hc3": fit.bse["predictor_z"],
                        "ci_low": ci.iloc[0],
                        "ci_high": ci.iloc[1],
                        "p_value": fit.pvalues["predictor_z"],
                        "r_squared": fit.rsquared,
                        "adj_r_squared": fit.rsquared_adj,
                    }
                )
            except Exception as exc:
                rows.append({**base, "status": f"{type(exc).__name__}: {exc}"})
    result = fdr_bh(pd.DataFrame(rows), "p_value")
    if not result.empty:
        result["significant_p05"] = result["p_value"] < ALPHA
        result["significant_fdr05"] = result["q_fdr_bh"] < ALPHA
    return result


def run(df: pd.DataFrame, individual_effectiveness: pd.DataFrame) -> dict:
    predictors = candidate_predictors(df)
    pre_questionnaire = pre_questionnaire_models(df)
    source = df.set_index(ID_COLUMN)
    valid_effectiveness = individual_effectiveness[individual_effectiveness["status"] == "ok"].copy()
    main_rows = []
    moderation_rows = []
    predictor_types = predictors.set_index("predictor")["type"].to_dict()
    for predictor in predictors["predictor"].tolist():
        questionnaire = predictor_types.get(predictor) == "questionnaire"
        predictor_values = source[predictor]
        for variable, subset in valid_effectiveness.groupby("variable"):
            data = subset.copy()
            data["predictor"] = data[ID_COLUMN].map(predictor_values)
            data["predictor_z"] = zscore(data["predictor"])
            data["group_experimental"] = (to_numeric(data[GROUP_COLUMN]) == 1).astype(float)
            data["age_z"] = zscore(data["age"])
            data["sex"] = data["sex"].astype(str).str.strip().replace({"nan": np.nan, "None": np.nan, "": np.nan})
            data["class_cov"] = data["class"].astype(str).str.strip().replace({"nan": np.nan, "None": np.nan, "": np.nan})
            data["effectiveness_pct"] = to_numeric(data["effectiveness_pct"])
            required = ["effectiveness_pct", "predictor_z", "group_experimental", "age_z"]
            if not questionnaire:
                required.extend(["sex", "class_cov"])
            data = data.dropna(subset=required)
            base = {"predictor": predictor, "outcome": variable, "n": len(data)}
            if len(data) < MIN_N or data["group_experimental"].nunique() < 2:
                main_rows.append({**base, "status": "insufficient_data"})
                moderation_rows.append({**base, "status": "insufficient_data"})
                continue
            for interaction, target in [(False, main_rows), (True, moderation_rows)]:
                try:
                    target.append({**base, "status": "ok", **fit_model(data, interaction, questionnaire)})
                except Exception as exc:
                    target.append({**base, "status": f"{type(exc).__name__}: {exc}"})

    main = fdr_bh(pd.DataFrame(main_rows), "p_value")
    moderation = fdr_bh(pd.DataFrame(moderation_rows), "p_value")
    for frame in [main, moderation]:
        if not frame.empty:
            frame["significant_p05"] = frame["p_value"] < ALPHA
            frame["significant_fdr05"] = frame["q_fdr_bh"] < ALPHA
    path = OUT_DIR / "predictor_models.xlsx"
    write_workbook(
        path,
        {
            "predictor_dictionary": predictors,
            "main_models": main,
            "moderation_models": moderation,
            "pre_questionnaire_models": pre_questionnaire,
            "significant_pre_questionnaire": pre_questionnaire[
                pre_questionnaire.get("significant_p05", False) == True
            ]
            if not pre_questionnaire.empty
            else pre_questionnaire,
            "significant_main": main[main.get("significant_p05", False) == True] if not main.empty else main,
            "significant_moderation": moderation[moderation.get("significant_p05", False) == True] if not moderation.empty else moderation,
        },
    )
    return {
        "predictors": predictors,
        "main": main,
        "moderation": moderation,
        "pre_questionnaire": pre_questionnaire,
        "files": [path],
    }
